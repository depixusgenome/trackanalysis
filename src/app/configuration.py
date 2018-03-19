#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from    pathlib                import Path
from    typing                 import Dict, Any
import  appdirs
from    utils.logconfig        import logToFile
from    utils.inspection       import getclass
from    view.keypress          import DpxKeyEvent
from    anastore.configuration import readconfig, writeconfig

CATCHERROR = True
class ConfigurationIO:
    """
    Read/Write configuration
    """
    def __init__(self, app) -> None:
        app          = getattr(app, 'MainControl', app)
        self.appname = getattr(app, 'APPNAME',     app)
        self.appsize = getattr(app, 'APPSIZE', [1200, 1000])

    def apppath(self) -> Path:
        "returns the path to local appdata directory"
        name = self.appname.replace(' ', '_').lower()
        return Path(appdirs.user_config_dir('depixus', 'depixus', name))

    def configpath(self, version, stem = None) -> Path:
        "returns the path to the config file"
        fname = ('autosave' if stem is None else stem)+'.txt'
        return self.apppath()/str(version)/fname

    def writeuserconfig(self, maps, name = None, saveall = False, **kwa):
        "writes the config"
        kwa['saveall'] = saveall
        writeconfig(maps, lambda i: self.configpath(i, name), **kwa)

    def readuserconfig(self, maps):
        "read the user config"
        def _upd(left, right):
            for i in set(left) & set(right):
                if isinstance(left[i], dict):
                    _upd(left[i], right[i])
                else:
                    left[i] = right[i]
            return left

        return _upd(_upd(maps, readconfig(self.configpath, maps = maps)),
                    readconfig(lambda i: self.configpath(i, 'userconfig'), maps = maps))

    def startup(self, maps):
        "starts the controler"
        self.writeuserconfig(maps, 'defaults',   index = 1, saveall   = True)
        self.writeuserconfig(maps, 'userconfig', index = 0, overwrite = False)
        return self.readuserconfig(maps)

    @classmethod
    def createview(cls, controls, views, name) -> type:
        "imports controls & returns the views & appname"
        get      = lambda i: getclass(i) if isinstance(i, str) else i
        controls = tuple(controls)

        controls = tuple(get(i) for i in controls)
        views    = tuple(get(i) for i in views)
        appname  = next((i.APPNAME for i in views if hasattr(i, 'APPNAME')),
                        cls(get(controls[0])))

        cnfcls   = cls
        class Main(*views): # type: ignore
            "The main view"
            APPNAME         = appname
            KeyPressManager = DpxKeyEvent
            MainControl     = type('MainControl', (controls[0],), dict(APPNAME = appname))
            @classmethod
            def launchkwargs(cls, **kwa) -> Dict[str, Any]:
                "updates kwargs used for launching the application"
                cnf   = cnfcls(cls)
                catch = getattr(cls.MainControl, 'CATCHERROR', CATCHERROR)
                maps  = {name:     {'appsize': cnf.appsize,
                                    'appname': cnf.appname.capitalize()},
                         'config': {'catcherror': catch}
                        }
                maps = cnf.readuserconfig(maps)

                setattr(cls.MainControl, 'CATCHERROR', maps['config']['catcherror'])
                kwa.setdefault("title",  maps[name]["appname"])
                kwa.setdefault("size",   maps[name]['appsize'])
                return kwa

            @classmethod
            def open(cls, doc, **kwa):
                "starts the application"
                ctrl = cls.MainControl(None)
                keys = cls.KeyPressManager(ctrl) if cls.KeyPressManager else None
                self = cls(ctrl, **kwa)
                ctrl.topview = self

                cls.__bases__[0].ismain(self, ctrl)
                ctrl.startup()

                if keys:
                    keys.observe(ctrl)
                for i in cls.__bases__:
                    getattr(i, 'observe', lambda *_: None)(self, ctrl)

                if keys:
                    keys.addtodoc(ctrl, doc)
                self.addtodoc(ctrl, doc)
                ctrl.handle('applicationstarted') # pylint: disable=protected-access
                return self

            def close(self):
                "closes the application"
                ctrl = getattr(self, '_ctrl', None)
                delattr(self, '_ctrl')
                if ctrl:
                    ctrl.close()
                super().close()

        logToFile(str(cls(Main).apppath()/"logs.txt"))
        return Main
