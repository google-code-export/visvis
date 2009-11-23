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

""" Module freezeHelp

Helps freezing apps made using visvis.

$Author: almar@SAS $
$Date: 2009-11-23 11:27:16 +0100 (Mon, 23 Nov 2009) $
$Rev: 1305 $

"""
import visvis as vv
import os, shutil

def copyResources(destPath):   
    """ Copy the visvis resource dir to the specified folder. 
    (The folder containing the frozen executable)"""
    # create folder (if required)
    destPath = os.path.join(destPath, 'visvisResources')
    if not os.path.isdir(destPath):
        os.makedirs(destPath)
    # copy files
    path = vv.misc.getResourceDir()
    for file in os.listdir(path):
        if file.startswith('.') or file.startswith('_'):
            continue
        shutil.copy(os.path.join(path,file), os.path.join(destPath,file))

def getIncludes(backendName):
    """ Get a list of includes to extend the 'includes' list
    with of py2exe or bbfreeze. The list contains:
    - the module of the specified backend 
    - all the functionnames, which are dynamically loaded and therefore 
      not included by default.
    - opengl stuff
    """
    includes = []
    # backend
    backendModule = 'visvis.backends.backend_'+ backendName
    includes.append(backendModule)
    if backendName == 'qt4':
        includes.extend(["sip", "PyQt4.QtCore", "PyQt4.QtGui"])
    # functions
    for funcName in vv.functions._functionNames:
        includes.append('visvis.functions.'+funcName)
    # opengl stuff
    tmp = ["nones", "strings","lists","numbers","ctypesarrays",
        "ctypesparameters", "ctypespointers", "numpymodule"]
    for i in tmp:
        includes.append("OpenGL.arrays."+i)
    includes.append("OpenGL.platform.win32")
    # done
    return includes
    
    