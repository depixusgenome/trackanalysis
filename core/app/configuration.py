#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Storing global properties"
from    pathlib                import Path
from    typing                 import Dict, Any, Type, TYPE_CHECKING, cast
import  appdirs
from    utils.logconfig        import logToFile
from    utils.inspection       import getclass
from    anastore.configuration import readconfig, writeconfig
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from .maincontrol          import BaseSuperController

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
        if not maps:
            maps = {}
        kwa['saveall'] = saveall
        writeconfig(maps, lambda i: self.configpath(i, name), **kwa)

    def readconfig(self, maps, name = None):
        "read a config"
        if name is None:
            return readconfig(self.configpath, maps = maps)
        return readconfig(lambda i: self.configpath(i, name), maps = maps)

    def readuserconfig(self, maps, update = False):
        "read the user config"

        autosave = self.readconfig(maps)
        userconf = self.readconfig(maps, "userconfig")
        if update:
            def _upd(left, right):
                if right:
                    left.update({i: j for i, j in right.items()
                                 if not isinstance(j, dict)})

                    for i, j in right.items():
                        if isinstance(j, dict):
                            _upd(left[i], j)

            _upd(maps, autosave)
            _upd(maps, userconf)
            return maps

        if not userconf or not autosave:
            return autosave if autosave else userconf if userconf else {}

        def _agg(left, right):
            if right:
                left.update({i: j for i, j in right.items()
                             if i not in left or not isinstance(j, dict)})

                for i, j in left.items():
                    if i in right and isinstance(j, dict):
                        _agg(j, right[i])

        return _agg(autosave, userconf)

    @classmethod
    def createview(cls, controls, views) -> type:
        "imports controls & returns the views & appname"
        get      = lambda i: getclass(i) if isinstance(i, str) else i

        controls = tuple(get(i) for i in controls)
        views    = tuple(get(i) for i in views if get(i))
        appname  = next((i.APPNAME for i in views if hasattr(i, 'APPNAME')), None)
        if appname is None:
            appname = views[0].__name__.replace('view', '')

        class Main: # type: ignore
            "The main view"
            APPNAME     = appname
            MainControl = cast(Type['BaseSuperController'],
                               type('MainControl', controls[:1],
                                    dict(APPNAME = appname)))
            VIEWS       = views
            def __init__(self, ctrl = None, **kwa):
                self.views = tuple(i(ctrl = ctrl, **kwa) for i in self.VIEWS)

            @classmethod
            def launchkwargs(cls, **kwa) -> Dict[str, Any]:
                "updates kwargs used for launching the application"
                return cls.MainControl.launchkwargs(**kwa)

            @classmethod
            def open(cls, doc, **kwa):
                "starts the application"
                return cls.MainControl.open(cls, doc, **kwa)

            def close(self):
                "closes the application"
                ctrl  = getattr(self, '_ctrl', None)
                views = getattr(self, 'views', ())
                if hasattr(self, '_ctrl'):
                    delattr(self, '_ctrl')
                if hasattr(self, 'views'):
                    delattr(self, 'views')
                if ctrl:
                    ctrl.close()

                for i in views:
                    if hasattr(i, 'close'):
                        i.close()

        logToFile(str(cls(Main).apppath()/"logs.txt"))
        return Main
