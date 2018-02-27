#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main controller"
import sys
from   pathlib                 import Path
from   typing                  import Dict, Any

import appdirs

from   control.event           import EmitPolicy
from   control.taskcontrol     import TaskController
from   control.globalscontrol  import GlobalsController
from   undo.control            import UndoController
from   utils.inspection        import getclass
from   utils.logconfig         import logToFile
from   .scripting              import orders

class SuperController:
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    APPNAME  = 'Track Analysis'
    FLEXXAPP = None
    def __init__(self, view):
        self.topview = view
        hdl: dict    = dict()
        self.globals = GlobalsController(handlers = hdl)
        self.tasks   = TaskController(handlers = hdl)
        self.undos   = UndoController(handlers = hdl)

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
        name = cls.APPNAME.replace(' ', '_').lower()
        return Path(appdirs.user_config_dir('depixus', 'depixus', name))

def createview(main, controls, views):
    "Creates a main view"
    for i in controls:
        if isinstance(i, str):
            getclass(i)

    views   = tuple(getclass(i) if isinstance(i, str) else i for i in views)
    appname = next((i.APPNAME for i in (main,)+views if hasattr(i, 'APPNAME')),
                   'Track Analysis')
    class Main(*(main,)+views): # type: ignore
        "The main view"
        APPNAME = appname
        class MainControl(SuperController):
            """
            Main controller: contains all sub-controllers.
            These share a common dictionnary of handlers
            """
            APPNAME = appname

        def __init__(self):
            "sets up the controller, then initializes the view"
            ctrl = self.MainControl(self)
            keys = getattr(self, 'KeyPressManager', lambda **_: None)(ctrl = ctrl)
            main.__init__(self, ctrl = ctrl, keys = keys)
            main.ismain(self)

            ctrl.startup()
            main.observe(self)
            for cls in views:
                cls.observe(self)

        def addtodoc(self, doc):
            "Adds one's self to doc"
            for mdl in orders().dynloads():
                getattr(sys.modules.get(mdl, None), 'document', lambda x: None)(doc)
            super().addtodoc(doc)

        @classmethod
        def launchkwargs(cls, **kwa) -> Dict[str, Any]:
            "updates kwargs used for launching the application"
            appname = getattr(cls.MainControl, 'APPNAME', 'track analysis')
            kwa.setdefault("title",  appname.capitalize())
            kwa.setdefault("size",  (1200, 1000))
            return kwa

    logToFile(str(Main.MainControl.apppath()/"logs.txt"))
    return Main
