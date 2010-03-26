#   This file is part of VISVIS.
#    
#   VISVIS is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Lesser General Public License as 
#   published by the Free Software Foundation, either version 3 of 
#   the License, or (at your option) any later version.
# 
#   VISVIS is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Lesser General Public License for more details.
# 
#   You should have received a copy of the GNU Lesser General Public 
#   License along with this program.  If not, see 
#   <http://www.gnu.org/licenses/>.
#
#   Copyright (C) 2009 Almar Klein

""" Module base

Defines the Wibject and Wobject classes, and some other 
(relatively small classes). 

More complex datatypes (like Line and Texture)
are defined in seperate modules.

$Author$
$Date$
$Rev$

"""

import OpenGL.GL as gl
import OpenGL.GL.ARB.shader_objects as gla
import OpenGL.GLU as glu

import numpy as np
import math, time
import weakref

from misc import Property, Range, OpenGLError, Transform_Base
from misc import Transform_Translate, Transform_Scale, Transform_Rotate
from misc import getColor
import events

from points import Pointset, Quaternion


class BaseObject(object):
    """ The base class for wibjects and wobjects.
    Instances of classes inherited from this class represent 
    something that can be drawn. 
    
    Wibjects and wobjects can have children and have a parent 
    (which can be None in which case they are in orphan and never 
    drawn). To change the structure, use the ".parent" property. 
    They also can be set visible/invisible using the property ".visible". 
    """
    
    def __init__(self, parent):
        # wheter or not the object has been destroyed
        self._destroyed = False
        # whether or not to draw the object
        self._visible = True
        # whether the object can be clicked
        self._hitTest = False
        # the parent object
        self._parent = None        
        # the children of this object
        self._children = []
        # the id of this object (can change on every draw)
        # used to determine over which object the mouse is.
        self._id = 0
        # a variable to indicate whether the mouse was pressed down here
        self._mousePressedDown = False
        
        # set parent
        self.parent = parent
        
        # create events
        self._eventMouseDown = events.EventMouseDown(self) 
        self._eventMouseUp = events.EventMouseUp(self)       
        self._eventDoubleClick = events.EventDoubleClick(self)
        self._eventEnter = events.EventEnter(self)
        self._eventLeave = events.EventLeave(self)        
        #
        self._eventMotion = events.EventMotion(self)
        self._eventKeyDown = events.EventKeyDown(self)
        self._eventKeyUp = events.EventKeyUp(self)
    
    
    @property
    def eventMouseDown(self):
        """ Fired when the mouse is pressed down on this object. (Also 
        fired the first click of a double click.) """
        return self._eventMouseDown
    @property
    def eventMouseUp(self):
        """ Fired when the mouse is released after having been clicked down
        on this object (even if the mouse is now not over the object). (Also
        fired on the first click of a double click.) """
        return self._eventMouseUp
    @property
    def eventDoubleClick(self):
        """ Fired when the mouse is double-clicked on this object. """
        return self._eventDoubleClick
    @property
    def eventEnter(self):
        """ Fired when the mouse enters this object or one of its children. """
        return self._eventEnter
    @property
    def eventLeave(self):
        """ Fired when the mouse leaves this object (and is also not over any
        of it's children). """
        return self._eventLeave
    
    @property
    def eventMotion(self):
        """ Fires when the mouse is moved over the object. Not fired when
        the mouse is over one of its children. """
        return self._eventMotion    
    @property
    def eventKeyDown(self):        
        """ Fires when the mouse is moved over the object. Not fired when
        the mouse is over one of its children. """
        return self._eventKeyDown    
    @property
    def eventKeyUp(self):        
        """ Fires when the mouse is moved over the object. Not fired when
        the mouse is over one of its children. """
        return self._eventKeyUp
    
    
    def _DrawTree(self, mode='normal', pickerHelper=None):
        """ Draw the wibject/wobject and all of its children. 
        shape can be an ObjectPickerHelper instance in which
        case only shape is drawn. 
        """
        # are we alive
        if self._destroyed:
            print "Warning, cannot draw destroyed object:", self
            return 
        # only draw if visible
        if not self.visible:
            return
        # transform
        gl.glPushMatrix()
        self._Transform()
        # draw self        
        if mode=='shape':
            if self.hitTest:
                clr = pickerHelper.GetColorFromId(self._id)
                self.OnDrawShape(clr)
        elif mode=='screen':
            self.OnDrawScreen()            
        elif mode=='fast':
            self.OnDrawFast()
        elif mode=='normal':
            self.OnDraw()
        else:
            raise Exception("Invalid mode for _DrawTree.")        
        # draw children
        for item in self._children:
            if hasattr(item, '_DrawTree'):
                item._DrawTree(mode,pickerHelper)
                
        # transform back
        gl.glPopMatrix()
    
    
    def Destroy(self, setContext=True):
        """ Destroy()
        Destroy the object.
          * Removes itself from the parent's children
          * Calls Destroy() on all its children
          * Calls OnDestroyGl and OnDestroy on itself
        
        Note1: do not overload, overload OnDestroy(). 
        Note2: it's best not to reuse destroyed objects. To temporary disable
        an object, better use "ob.parent=None", or "ob.visible=False".
        """
        # We must make this the current OpenGL context because OnDestroy 
        # methods of objects may want to remove textures etc.
        # When you do not do this, you can get really weird bugs.
        # This works nice, the children will not need to do this,
        # as when they try, THIS object is already detached and fig is None.
        if setContext:
            fig = self.GetFigure()
            if fig:
                fig._SetCurrent()
        
        # Destroy children. This will unwind to the leafs of the tree, and
        # thus call OnDestroy() on childless objects only. This means the
        # parent of all objects remain intact, which can be necessary for
        # some objects to clean up nicely. 
        for child in self.children:
            child.Destroy(False)
        
        # Actual destroy
        self.OnDestroyGl()
        self.OnDestroy()
        self._destroyed = True
        
        # Leave home (using the property causes recursion)        
        if hasattr(self._parent, '_children'):
            while self in self._parent._children:
                self._parent._children.remove(self)                
        if hasattr(self._parent, '_wobjects'):
            while self in self._parent._wobjects:
                self._parent._wobjects.remove(self)
        self._parent = None
    
    
    def DestroyGl(self, setContext=True):
        """ DestroyGl() 
        Destroy the OpenGl objects managed by this object.
          * Calls DestroyGl() on all its children.
          * Calls OnDestroyGl() on itself.
        Note: do not overload, overload OnDestroyGl().
        """
        
        # make the right openGlcontext current
        if setContext:
            fig = self.GetFigure()
            if fig:
                fig._SetCurrent()
        
        # let children clean up their openGl stuff
        for child in self._children:
            child.DestroyGl(False)
        
        # Clean up our own bits
        self.OnDestroyGl()
    
    
    def __del__(self):
        self.Destroy()
    
    
    def _Transform(self):
        """ Add transformations to modelview matrix such that the object
        is displayed properly. """
        pass # implemented diffently by the wibject and wobject class
    
    
    def OnDraw(self):
        """ OnDraw()
        Perform the opengl commands to draw this wibject/wobject. 
        Objects should overload this method to draw themselves.
        """
        pass
    
    def OnDrawFast(self):
        """ OnDrawFast()
        Overload this to provide a faster version to draw (but
        less pretty), which is called when the scene is zoomed/translated.
        By default, this calls OnDraw()
        """
        self.OnDraw()    
    
    def OnDrawShape(self, color):
        """ OnDrawShape(color)
        Perform  the opengl commands to draw the shape of the object
        in the given color. 
        If not implemented, the object cannot be picked.
        """
        pass
    
    def OnDrawScreen(self):
        """ OnDrawScreen()
        Draw in screen coordinates. To be used for wobjects that
        need drawing in screen coordinates (like text). Wibjects are 
        always drawn in screen coordinates (using OnDraw)."""
        pass
        
    def OnDestroy(self):
        """ OnDestroy()
        Overload this to clean up any resources other than the GL objects. 
        """
        for att in self.__dict__.values():
            if isinstance(att, events.BaseEvent):
                att.Unbind()
             
    
    def OnDestroyGl(self):
        """ OnDestroyGl()
        Overload this to clean up any OpenGl resources. 
        """
        pass 
    
    @Property
    def visible():
        """ Get/Set whether the object should be drawn or not. 
        If set to False, the hittest is also not performed. """
        def fget(self):
            return self._visible
        def fset(self, value):
            self._visible = bool(value)
    
    @Property
    def hitTest():
        """ Get/Set whether mouse events are generated for this object. """
        def fget(self):
            return self._hitTest
        def fset(self, value):
            self._hitTest = bool(value)
    
    
    @Property
    def parent():
        """ Get/Set the parent of this object. Use this to change the
        tree structure of your visualization objects (for example move a line
        from one axes to another).
        """
        def fget(self):
            return self._parent
        def fset(self,value):
            
            # init lists to update
            parentChildren = None
            if hasattr(value, '_children'):
                parentChildren = value._children
            
            # check if this is a valid parent
            tmp = "Cannot change to that parent, "
            if value is None:
                # an object can be an orphan
                pass 
            elif value is self:
                # an object cannot be its own parent
                raise TypeError(tmp+"because that is the object itself!")
            elif isinstance(value, Wibject):
                # some wibject parents can hold wobjects
                if isinstance(self, Wobject):
                    if hasattr(value, '_wobjects'):
                        parentChildren = value._wobjects
                    else:
                        tmp2 = "a wobject can only have a wibject-parent "
                        raise TypeError(tmp+tmp2+"if it can hold wobjects!")
            elif isinstance(value, Wobject):
                # a wobject can only hold wobjects
                if isinstance(self, Wibject):
                    raise TypeError(tmp+"a wibject cant have a wobject-parent!")
            else:            
                raise TypeError(tmp+"it is not a wibject or wobject or None!")
            
            # remove from parents childrens list 
            if hasattr(self._parent, '_children'):
                while self in self._parent._children:
                    self._parent._children.remove(self)                
            if hasattr(self._parent, '_wobjects'):
                while self in self._parent._wobjects:
                    self._parent._wobjects.remove(self)
            
            # Should we destroy GL objects (because we are removed 
            # from an OpenGL context)? 
            figure1 = self.GetFigure()
            figure2 = None
            if hasattr(value, 'GetFigure'):
                figure2 = value.GetFigure()
            if figure1 and (figure1 is not figure2):
                self.DestroyGl()
            
            # set and add to new parent
            self._parent = value
            if parentChildren is not None:
                parentChildren.append(self)
    
    
    @property
    def children(self):
        """ Get a shallow copy of the list of children. 
        """
        return [child for child in self._children]
    
    
    def GetFigure(self):
        """ GetFigure()
        Get the figure that this object is part of.
        The figure represents the OpenGL context.
        Returns None if it has no figure.
        """ 
        # init
        iter = 0
        object = self
        # search
        while hasattr(object,'parent'):
            iter +=1
            if object.parent is None:
                break
            if iter > 100:
                break
            object = object.parent
        # check
        if object.parent is None and hasattr(object, '_SwapBuffers'):
            return object
        else:
            return None
    
    
    def Draw(self, fast=False):
        """ Draw(fast=False)
        Calls Draw on the figure if this object is inside one.
        """
        fig = self.GetFigure()
        if fig:
            fig.Draw()
    
    
    def FindObjects(self, spec):
        """ FindObjects(pattern)
        Find the objects in this objects' children, and its childrens
        children, etc, that correspond to the given pattern. 
        
        The pattern can be a class or tuple of classes, an attribute name 
        (as a string) that the objects should have, or a callable that 
        returns True or False given an object. For example
        'lambda x: ininstance(x, cls)' will do the same as giving a class.
        
        Searches in the list of wobjects if the object is a wibject and
        has a _wobject property (like the Axes wibject).
        """
        
        
        # Parse input
        if hasattr(spec, 'func_name'):
            callback = spec
        elif isinstance(spec, (type, tuple)):
            callback = lambda x: isinstance(x, spec)
        elif isinstance(spec, basestring):
            callback = lambda x: hasattr(x, spec)
        elif hasattr(spec, '__call__'):
            callback = spec # other callable
        else:
            raise ValueError('Invalid argument for FindObjects')
        
        # Init list with result
        result = []
        
        # todo: use generator expression?
        # Try all children recursively
        for child in self._children:
            if callback(child):
                result.append(child)
            result.extend( child.FindObjects(callback) )
        if hasattr(self, '_wobjects'):
            for child in self._wobjects:
                if callback(child):
                    result.append(child)
                result.extend( child.FindObjects(callback) )
        
        # Done
        return result
    
    
    def GetWeakref(self):
        """ GetWeakref()        
        Get a weak reference to this object. 
        Call the weakref to obtain the real reference (or None if it's dead).
        """
        return weakref.ref( self )


class Wibject(BaseObject):
    """ A visvis.Wibject (widget object) is a 2D object drawn in 
    screen coordinates. A Figure is a widget and so is an Axes or a 
    PushButton. Using their structure, it is quite easy to build widgets 
    from the basic components. Wibjects have a position property to 
    set their location and size. They also have a background color 
    and multiple event properties.
    
    This class may also be used as a container object for other wibjects. 
    An instance of this class has no visual appearance. The Box class 
    implements drawing a rectangle with an edge.
    """
    
    def __init__(self, parent):
        BaseObject.__init__(self, parent)
        
        # the position of the widget within its parent        
        self._position = Position( 10,10,50,50, self)
        
        # colors and edge
        self._bgcolor = (0.8,0.8,0.8)
        
        # event for position
        self._eventPosition = events.EventPosition(self)
    
    
    @property
    def eventPosition(self):
        """ Fired when the position (or size) of this wibject changes. """ 
        return self._eventPosition
    
    
    @Property
    def position():
        """ Get/Set the position of this wibject. Setting can be done
        by supplying either a 2-element tuple or list to only change
        the location, or a 4-element tuple or list to change location
        and size.
        
        See the docs of the vv.base.Position class for more information.
        """
        def fget(self):
            return self._position
        def fset(self, value):
            self._position.Set(value)
    
    
    @Property
    def bgcolor():
        """ Get/Set the background color of the wibject. """
        def fget(self):
            return self._bgcolor
        def fset(self, value):
            self._bgcolor = getColor(value, 'setting bgcolor')
    
    
    def _Transform(self):
        """ _Transform()
        Apply a translation such that the wibject is 
        drawn in the correct place. 
        """
        # skip if we are on top
        if not self.parent:
            return            
        # get posision in screen coordinates
        pos = self.position
        # apply
        gl.glTranslatef(pos.left,pos.top,0.0)


    def OnDrawShape(self, clr):
        # Implementation of the OnDrawShape method.
        gl.glColor(clr[0], clr[1], clr[2], 1.0)
        w,h = self.position.size
        gl.glBegin(gl.GL_POLYGON)
        gl.glVertex2f(0,0)
        gl.glVertex2f(0,h)
        gl.glVertex2f(w,h)
        gl.glVertex2f(w,0)
        gl.glEnd()



class Wobject(BaseObject):
    """ A visvis.Wobject (world object) is a visual element that 
    is drawn in 3D world coordinates (in the scene). Wobjects can be 
    children of other wobjects or of an Axes object (which is a 
    wibject). 
    
    To each wobject, several transformations can be applied, 
    which are also applied to its children. This way complex models can 
    be build. For example in a robot arm the fingers would be children 
    of the hand, so if the hand moves or rotates, the fingers move along 
    automatically. The fingers can then also be moved without affecting 
    the hand or other fingers. 
    
    The transformations are represented by Transform_* objects in 
    the list named "transformations". The transformations are applied
    in the order as they appear in the list. 
    """
    
    def __init__(self, parent):
        BaseObject.__init__(self, parent)
        
        # the transformations applied to the object
        self._transformations = []
    
    
    @property
    def transformations(self):
        """ Get the list of transformations of this wobject. These
        can be Transform_Translate, Transform_Scale, or Transform_Rotate
        instances.
        """        
        return self._transformations
    
    
    def GetAxes(self):
        """ GetAxes()
        Get the axes in which this wobject resides. 
        Note that this is not necesarily an Axes instance (like the line
        objects in the Legend wibject).
        """
        par = self.parent
        if par is None:
            return None# raise TypeError("Cannot find axes!")
        while not isinstance(par, Wibject):            
            par = par.parent
            if par is None:
                return None
                #tmp = "Cannot find axes, error in Wobject/Wibject tree!"
                #raise TypeError(tmp)
        return par
    
    
    def Draw(self, fast=False):
        """ Draw(fast=False)
        Calls Draw on the axes if this object is inside one.
        """
        fig = self.GetAxes()
        if fig:
            fig.Draw()
    
    
    def _GetLimits(self, *args):
        """ _GetLimits()
        Get the limits in world coordinates between which the object 
        exists. This is used by the Axes class to set the camera correctly.
        If None is returned, the limits are undefined. 
        Inheriting Wobject classes should overload this method. But they can
        use this method to take all transformations into account by giving
        the cornerpoints of the untransformed object:
        xlim, ylim, zlim = Wobject._GetLimits(self, x1, x2, y1, y2, z1, z2)
        """
        
        # Examine args
        if not args:
            return None
        elif len(args) != 6:
            raise ValueError("_Getlimits expects 0 or 6 arguments.")
        
        # Make pointset of six cornerpoints
        x1, x2, y1, y2, z1, z2 = args
        pp = Pointset(3)
        for x in [x1, x2]:
            for y in [y1, y2]:
                for z in [z1, z2]:
                    pp.Append(x,y,z)
        
        # Transform these points
        for i in range(len(pp)):
            p = pp[i]
            for t in reversed(self._transformations):
                if isinstance(t, Transform_Translate):
                    p.x += t.dx
                    p.y += t.dy
                    p.z += t.dz
                elif isinstance(t, Transform_Scale):
                    p.x *= t.sx
                    p.y *= t.sy
                    p.z *= t.sz
                elif isinstance(t, Transform_Rotate):
                    angle = t.angle * np.pi / 180.0
                    q = Quaternion.CreateFromAxisAngle(angle, t.ax, t.ay, t.az)
                    p = q.RotatePoint(p)
            # Update
            pp[i] = p                    
        
        # Return limits (say nothing about z)
        xlim = Range( pp[:,0].min(), pp[:,0].max() )
        ylim = Range( pp[:,1].min(), pp[:,1].max() )
        zlim = Range( pp[:,2].min(), pp[:,2].max() )
        return xlim, ylim, zlim
    
    
    def _Transform(self):
        """ _Transform()
        Apply all listed transformations of this wobject. 
        """   
        for t in self.transformations:
            if not isinstance(t, Transform_Base):
                continue
            elif isinstance(t, Transform_Translate):
                gl.glTranslate(t.dx, t.dy, t.dz)
            elif isinstance(t, Transform_Scale):
                gl.glScale(t.sx, t.sy, t.sz)
            elif isinstance(t, Transform_Rotate):
                gl.glRotate(t.angle, t.ax, t.ay, t.az)


## Help classes

class Position(object):
    """ Position(x,y,w,h, wibject_instance)
    
    The position class stores and manages the position of wibjects. Each 
    wibject has one Position instance associated with it, which can be 
    obtained (and updated) using its position property.
    
    The position is represented using four values: x, y, w, h. The Position
    object can also be indexed to get or set these four values.
    
    Each element (x,y,w,h) can be either:
      * The integer amount of pixels relative to the wibjects parent's position. 
      * The fractional amount (float value between 0.0 and 1.0) of the parent's width or height.
    
    Each value can be negative. For x and y this simply means a negative 
    offset from the parent's left and top. For the width and height the 
    difference from the parent's full width/height is taken.
    
    An example: a position (-10, 0.5, 150,-100), with a parent's size of 
    (500,500) is equal to (-10, 250, 150, 400) in pixels.
    
    Remarks:
      * fractional, integer and negative values may be mixed.
      * x and y are considered fractional on <-1, 1> 
      * w and h are considered fractional on [-1, 1]    
      * the value 0 can always be considered to be in pixels 
    
    The position class also implements several "long-named" properties that
    express the position in pixel coordinates. Internally a version in pixel
    coordinates is buffered, which is kept up to date. These long-named 
    (read-only) properties are:
    left, top, right, bottom, width, height,
    
    Further, there are a set of properties which express the position in 
    absolute coordinates (not relative to the wibject's parent):
    absLeft, absTop, absRight, absBottom    
    
    Finally, there are properties that return a two-element tuple:
    topLeft, bottomRight, absTopLeft, absBottomRight, size
    
    The method InPixels() returns a (copy) Position object which represents
    the position in pixels.
    
    """
    
    def __init__(self, x, y, w, h, owner):
        
        # test owner
        if not isinstance(owner , Wibject):
            raise ValueError('A positions owner can only be a wibject.')
        
        # set
        self._x, self._y, self._w, self._h = x, y, w, h
        
        # store owner using a weak reference
        self._owner = weakref.ref(owner) 
        
        # init position in pixels and absolute (as a tuples)
        self._inpixels = None
        self._absolute = None
        
        # do not _update() here, beacause the owner will not have assigned
        # this object to its _position attribute yet.
        
        # but we can calculate our own pixels
        self._CalculateInPixels()
    
    
    def Copy(self):
        """ Copy()
        Make a copy. Otherwise you'll point to the same object! """
        p = Position(self._x, self._y, self._w, self._h, self._owner())
        p._inpixels = self._inpixels
        p._absolute = self._absolute
        return p
    
    
    def InPixels(self):
        """ InPixels()
        Return a copy, but in pixel coordinates. """
        p = Position(self.left,self.top,self.width,self.height, self._owner())
        p._inpixels = self._inpixels
        p._absolute = self._absolute
        return p
    
    
    def __repr__(self):
        return "<Position %1.2f, %1.2f,  %1.2f, %1.2f>" % (
            self.x, self.y, self.w, self.h)
    
    
    ## For keeping _inpixels up-to-date
    
    
    def _Update(self):
        """ _Update()
        Re-obtain the position in pixels. If the obtained position
        differs from the current position-in-pixels, _Changed()
        is called.
        """
        
        # get old version, obtain and store new version
        ip1 = self._inpixels + self._absolute
        self._CalculateInPixels()
        ip2 = self._inpixels + self._absolute
        
        if ip2:
            if ip1 != ip2: # also if ip1 is None
                self._Changed()
    
    
    def _Changed(self):
        """ _Changed()
        To be called when the position was changed. 
        Will fire the owners eventPosition and will call
        _Update() on the position objects of all the owners
        children.
        """
        # only notify if this is THE position of the owner (not a copy)
        owner = self._owner()
        if owner and owner._position is self:           
            if hasattr(owner, 'eventPosition'):
                owner.eventPosition.Fire()
                #print 'firing position event for', owner
            for child in owner._children:
                if hasattr(child, '_position'):
                    child._position._Update()
    
    
    def _GetFractionals(self):
        """ Get a list which items are considered relative.         
        Also int()'s the items which are not.
        """
        # init
        fractionals = [0,0,0,0]        
        # test
        for i in range(2):
            if self[i] > -1 and self[i] < 1 and self[i]!=0:
                fractionals[i] = 1
        for i in range(2,4):            
            if self[i] >= -1 and self[i] <= 1 and self[i]!=0:
                fractionals[i] = 1
        # return
        return fractionals
    
    
    def _CalculateInPixels(self):
        """ Return the position in screen coordinates as a tuple. 
        """
        
        # to test if this is easy
        fractionals = self._GetFractionals()
        negatives = [int(self[i]<0) for i in range(4)]
        
        # get owner
        owner = self._owner()
        
        # if owner is a figure, it cannot have relative values
        if hasattr(owner, '_SwapBuffers'):
            self._inpixels = (self._x, self._y, self._w, self._h)
            self._absolute = self._inpixels 
            return
        
        # test if we can calculate
        if not isinstance(owner, Wibject):
            raise Exception("Can only calculate the position in pixels"+
                            " if the position instance is owned by a wibject!")
        # else, the owner must have a parent...
        if owner.parent is None:
            print owner
            raise Exception("Can only calculate the position in pixels"+
                            " if the owner has a parent!")
        
        # get width/height of parent
        ppos = owner.parent.position
        whwh = ppos.width, ppos.height
        whwh = (whwh[0], whwh[1], whwh[0], whwh[1])
        
        # calculate!
        pos = [self._x, self._y, self._w, self._h]
        if max(fractionals)==0 and max(negatives)==0:
            pass # no need to calculate
        else:
            for i in range(4):
                if fractionals[i]:
                    pos[i] = pos[i]*whwh[i]
                if i>1 and negatives[i]:
                    pos[i] = whwh[i] + pos[i]
                # make sure it's int (even if user supplied floats > 1)
                pos[i] = int(pos[i])
        
        # abs pos is based on the inpixels version, but x,y corrected. 
        apos = [p for p in pos]
        if ppos._owner().parent:
            apos[0] += ppos.absLeft
            apos[1] += ppos.absTop
        
        # store
        self._inpixels = tuple(pos)
        self._absolute = tuple(apos)
    
    
    ## For getting and setting
    
    def Set(self, *args):
        """ Set(x, y, w, h) or Set(x,y)
        Set x, y, and optionally w an h.
        """
        
        # if tuple or list was given
        if len(args)==1 and hasattr(args[0],'__len__'):
            args = args[0]
        
        # apply
        if len(args)==2:
            self._x = args[0]
            self._y = args[1]
        elif len(args)==4:
            self._x = args[0]
            self._y = args[1]
            self._w = args[2]
            self._h = args[3]
        else:
            raise ValueError("Invalid number of arguments to position.Set().")
        
        # we need an update now
        self._Update()
    
    
    def Correct(self, dx=0, dy=0, dw=0, dh=0):
        """ Correct the position by suplying a delta amount of pixels.
        The correction is only applied if the attribute is in pixels.
        """
        
        # get fractionals
        fractionals = self._GetFractionals()
        
        # apply correction if we can
        if dx and not fractionals[0]:
            self._x += int(dx) 
        if dy and not fractionals[1]:
            self._y += int(dy)
        if dw and not fractionals[2]:
            self._w += int(dw) 
        if dh and not fractionals[3]:
            self._h += int(dh) 
        
        # we need an update now
        self._Update()
    
    
    def __getitem__(self,index):
        if not isinstance(index,int):
            raise IndexError("Position only accepts single indices!")        
        if index==0: return self._x
        elif index==1: return self._y
        elif index==2: return self._w
        elif index==3: return self._h
        else:
            raise IndexError("Position only accepts indices 0,1,2,3!")
    
    
    def __setitem__(self,index, value):
        if not isinstance(index,int):
            raise IndexError("Position only accepts single indices!")
        if index==0: self._x = value
        elif index==1: self._y = value
        elif index==2: self._w = value
        elif index==3: self._h = value
        else:
            raise IndexError("Position only accepts indices 0,1,2,3!")
        # we need an update now
        self._Update()
    
    
    @Property
    def x():
        """ Get/Set the x-element of the position. This value can be 
        an integer value or a float expressing the x-position as a fraction 
        of the parent's width. The value can also be negative. """
        def fget(self):
            return self._x
        def fset(self,value):
            self._x = value
            self._Update()
    
    @Property
    def y():
        """ Get/Set the y-element of the position. This value can be 
        an integer value or a float expressing the y-position as a fraction 
        of the parent's height. The value can also be negative. """
        def fget(self):
            return self._y
        def fset(self,value):
            self._y = value
            self._Update()
    
    @Property
    def w():
        """ Get/Set the w-element of the position. This value can be 
        an integer value or a float expressing the width as a fraction 
        of the parent's width. The value can also be negative, in which
        case it's subtracted from the parent's width. """
        def fget(self):
            return self._w
        def fset(self,value):
            self._w = value
            self._Update()
    
    @Property
    def h():
        """ Get/Set the h-element of the position. This value can be 
        an integer value or a float expressing the height as a fraction 
        of the parent's height. The value can also be negative, in which
        case it's subtracted from the parent's height. """
        def fget(self):
            return self._h
        def fset(self,value):
            self._h = value
            self._Update()
    
    ## Long names properties expressed in pixels
    
    @property
    def left(self):
        """ Get the x-element of the position, expressed in pixels. """
        tmp = self._inpixels
        return tmp[0]
    
    @property
    def top(self):
        """ Get the y-element of the position, expressed in pixels. """
        tmp = self._inpixels
        return tmp[1]
    
    @property
    def width(self):
        """ Get the w-element of the position, expressed in pixels. """
        tmp = self._inpixels
        return tmp[2]
    
    @property
    def height(self):
        """ Get the h-element of the position, expressed in pixels. """
        tmp = self._inpixels
        return tmp[3]
    
    @property
    def right(self):
        """ Get left+width. """
        tmp = self._inpixels
        return tmp[0] + tmp[2]
    
    @property
    def bottom(self):
        """ Get top+height. """
        tmp = self._inpixels
        return tmp[1] + tmp[3]
    
    @property
    def topLeft(self):
        """ Get a tuple (left, top). """
        tmp = self._inpixels
        return tmp[0], tmp[1]
    
    @property
    def bottomRight(self):
        """ Get a tuple (right, bottom). """
        tmp = self._inpixels
        return tmp[0] + tmp[2], tmp[1] + tmp[3]
    
    @property
    def size(self):
        """ Get a tuple (width, height). """
        tmp = self._inpixels
        return tmp[2], tmp[3]
    
    ## More long names for absolute position
    
    @property
    def absLeft(self):
        """ Get the x-element of the position, expressed in absolute pixels
        instead of relative to the parent. """
        tmp = self._absolute
        return tmp[0]
    
    @property
    def absTop(self):
        """ Get the y-element of the position, expressed in absolute pixels
        instead of relative to the parent. """
        tmp = self._absolute
        return tmp[1]
    
    @property
    def absTopLeft(self):
        """ Get a tuple (absLeft, absTop). """
        tmp = self._absolute
        return tmp[0], tmp[1]
    
    @property
    def absRight(self):
        """ Get absLeft+width. """
        tmp = self._absolute
        return tmp[0] + tmp[2]
    
    @property
    def absBottom(self):
        """ Get absTop+height. """
        tmp = self._absolute
        return tmp[1] + tmp[3]
    
    @property
    def absBottomRight(self):
        """ Get a tuple (right, bottom). """
        tmp = self._absolute
        return tmp[0] + tmp[2], tmp[1] + tmp[3]



## More simple wibjects and wobjects
# box must be defined here as it is used by textRender.Label
    
class Box(Wibject):
    """ A simple, multi-purpose, rectangle object.
    It implements functionality to draw itself. Most wibjects will
    actually inherit from Box, rather than from Wibject.
    """
    def __init__(self, parent):
        Wibject.__init__(self, parent)
        self._edgeColor = (0,0,0)
        self._edgeWidth = 1.0
    
    @Property
    def edgeColor():
        """ Get/Set the edge color of the wibject. """
        def fget(self):
            return self._edgeColor
        def fset(self, value):
            self._edgeColor = getColor(value, 'setting edgeColor')
    
    @Property
    def edgeWidth():
        """ Get/Set the edge width of the wibject. """
        def fget(self):
            return self._edgeWidth
        def fset(self, value):            
            self._edgeWidth = float(value)
    
    def _GetBgcolorToDraw(self):
        """ _GetBgcolorToDraw()
        Can be overloaded to indicate mouse over in buttons. """
        return self._bgcolor
    
    def OnDraw(self, fast=False):
        
        # get dimensions        
        w,h = self.position.size
        
        # draw plane
        if self._bgcolor:        
            clr = self._GetBgcolorToDraw()
            gl.glColor(clr[0], clr[1], clr[2], 1.0)            
            #
            gl.glBegin(gl.GL_POLYGON)
            gl.glVertex2f(0,0)
            gl.glVertex2f(0,h)
            gl.glVertex2f(w,h)
            gl.glVertex2f(w,0)
            gl.glEnd()
        
        # prepare                
        gl.glDisable(gl.GL_LINE_SMOOTH)
        
        # draw edges        
        if self.edgeWidth and self.edgeColor:
            clr = self.edgeColor
            gl.glColor(clr[0], clr[1], clr[2], 1.0)
            gl.glLineWidth(self.edgeWidth)
            #
            gl.glBegin(gl.GL_LINE_LOOP)
            gl.glVertex2f(0,0)
            gl.glVertex2f(0,h)
            gl.glVertex2f(w,h)
            gl.glVertex2f(w,0)
            gl.glEnd()
        
        # clean up        
        gl.glEnable(gl.GL_LINE_SMOOTH)
        
