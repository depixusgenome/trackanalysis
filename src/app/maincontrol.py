#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main controller"
from   pathlib                 import Path
import appdirs
from   control.taskcontrol     import TaskController
from   control.globalscontrol  import GlobalsController
from   undo.control            import UndoController
from   .scripting              import orders

class MainControl:
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    ISAPP    = False
    APPNAME  = 'Track Analysis'
    def __init__(self, view):
        self.topview = view
        hdl: dict    = dict()
        self.globals = GlobalsController(handlers = hdl)
        self.tasks   = TaskController(handlers = hdl)
        self.undos   = UndoController(handlers = hdl)

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
        fname = ('autosave' if stem is None else stem)+'.txt'
        return cls.apppath()/str(version)/fname

    def readuserconfig(self):
        """
        reads the config: first the stuff saved automatically, then
        anything the user wishes to impose.
        """
        ctrl = self.globals
        ctrl.readconfig(self.configpath)
        ctrl.readconfig(self.configpath, lambda i: self.configpath(i, 'userconfig'))
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
        self.writeuserconfig()
        self.globals.close()
        self.tasks.close()
        self.undos.close()

    @classmethod
    def apppath(cls) -> Path:
        "returns the path to local appdata directory"
        name = cls.APPNAME.replace(' ', '_').lower()
        return Path(appdirs.user_config_dir('depixus', 'depixus', name))
