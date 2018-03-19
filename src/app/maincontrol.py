#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main controller"
import sys
from   pathlib                 import Path

from   control.event           import EmitPolicy
from   control.taskcontrol     import TaskController
from   control.globalscontrol  import GlobalsController
from   control.decentralized   import DecentralizedController
from   control.action          import ActionDescriptor
from   undo.control            import UndoController
from   .configuration          import ConfigurationIO
from   .scripting              import orders

class SuperController:
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    APPNAME     = 'Track Analysis'
    APPSIZE     = [1200, 1000]
    FLEXXAPP    = None
    action      = ActionDescriptor()
    computation = ActionDescriptor()
    def __init__(self, view):
        self.topview = view
        hdl: dict    = dict()
        self.globals = self.__newglobals(handlers = hdl)
        self.tasks   = TaskController(handlers = hdl)
        self.undos   = UndoController(handlers = hdl)
        self.theme   = DecentralizedController() # everything static settings
        self.display = DecentralizedController() # everything dynamic settings

    emitpolicy = EmitPolicy

    def __undos__(self):
        yield from self.tasks.__undos__()
        yield from self.globals.__undos__()
        yield from self.undos.__undos__()

    def observe(self, *args, **kwa):
        "observe an event"
        return self.tasks.observe(*args, **kwa)

    def handle(self, *args, **kwa):
        "handle an event"
        return self.tasks.handle(*args, **kwa)

    @classmethod
    def configpath(cls, version, stem = None) -> Path:
        "returns the path to the config file"
        return ConfigurationIO(cls.APPNAME).configpath(version, stem)

    @classmethod
    def __newglobals(cls, **kwa) -> GlobalsController:
        "create new globals control"
        glob  = GlobalsController(**kwa)
        glob.css.defaults = {'appsize': cls.APPSIZE, 'appname': cls.APPNAME.capitalize()}
        return glob

    @classmethod
    def setupglobals(cls, glob = None):
        """
        reads the config: first the stuff saved automatically, then
        anything the user wishes to impose.
        """
        if glob is None:
            glob = cls.__newglobals()

        cpath = cls.configpath
        glob.readconfig(cpath)
        glob.readconfig(lambda i: cpath(i, 'userconfig'))
        return glob

    def readuserconfig(self):
        """
        reads the config: first the stuff saved automatically, then
        anything the user wishes to impose.
        """
        self.setupglobals(self.globals)
        orders().config(self)

    def writeuserconfig(self, name = None, saveall = False, **kwa):
        "writes the config"
        kwa['saveall'] = saveall
        ctrl = self.globals # pylint: disable=no-member
        ctrl.writeconfig(lambda i: self.configpath(i, name), **kwa)

    def startup(self):
        "starts the controler"
        self.writeuserconfig('defaults',   index = 1, saveall   = True)
        self.writeuserconfig('userconfig', index = 0, overwrite = False)
        self.readuserconfig()
        self.tasks.setup(self)

    def close(self):
        "remove controller"
        top, self.topview = self.topview, None
        if top is None:
            return

        self.writeuserconfig()
        self.globals.close()
        self.tasks.close()
        self.undos.close()
        top.close()
        if self.FLEXXAPP:
            self.FLEXXAPP.close()

    @classmethod
    def apppath(cls) -> Path:
        "returns the path to local appdata directory"
        return ConfigurationIO(cls.APPNAME).apppath()

def createview(main, controls, views):
    "Creates a main view"
    cls = ConfigurationIO.createview((SuperController,)+controls, (main,)+views, 'css')
    def addtodoc(self, ctrl, doc):
        "Adds one's self to doc"
        for mdl in orders().dynloads():
            getattr(sys.modules.get(mdl, None), 'document', lambda x: None)(doc)

        add = next((getattr(i, 'addtodoc') for i in cls.__bases__ if hasattr(i, 'addtodoc')))
        add(self, ctrl, doc)

    setattr(cls, 'addtodoc', addtodoc)
    return cls
