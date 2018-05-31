#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The main controller"
import sys
from   typing                  import Dict, Any

from   bokeh.themes            import Theme
from   bokeh.layouts           import layout


from   control.event           import EmitPolicy
from   control.taskcontrol     import TaskController
from   control.decentralized   import DecentralizedController
from   control.action          import ActionDescriptor
from   undo.control            import UndoController
from   view.keypress           import DpxKeyEvent
from   model.maintheme         import MainTheme
from   .configuration          import ConfigurationIO
from   .scripting              import orders

class DisplayController(DecentralizedController):
    "All temporary information related to one application run"
    CATCHERROR = True

class ThemeController(DecentralizedController):
    "All static information that should remain from application run to application run"

class BaseSuperController:
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    APPNAME     = 'Track Analysis'
    APPSIZE     = [1200, 1000]
    FLEXXAPP    = None
    action      = ActionDescriptor()
    computation = ActionDescriptor()
    def __init__(self, view, **kwa):
        self.topview = view
        self.undos   = UndoController(**kwa)
        self.theme   = ThemeController()
        self.theme.add(MainTheme())
        self.display = DisplayController()
        self._config_counts = [False]


    emitpolicy = EmitPolicy

    def __undos__(self, wrapper):
        for i in self.__dict__.values():
            getattr(i, '__undos__', lambda _: None)(wrapper)

    @classmethod
    def open(cls, viewcls, doc, **kwa):
        "starts the application"
        # pylint: disable=protected-access
        return cls(None)._open(viewcls, doc, kwa)

    def close(self):
        "remove controller"
        top, self.topview = self.topview, None
        if top is None:
            return

        self.writeuserconfig()
        for i in tuple(self.__dict__.values()) + (top, self.FLEXXAPP):
            getattr(i, 'close', lambda : None)()

    def writeuserconfig(self, name = None, saveall = False, **kwa):
        "writes the config"
        ConfigurationIO(self).writeuserconfig(self._getmaps(), name, saveall, **kwa)

    @classmethod
    def launchkwargs(cls, **kwa) -> Dict[str, Any]:
        "updates kwargs used for launching the application"
        cnf   = ConfigurationIO(cls)
        maps  = {'theme': {'appsize': cnf.appsize, 'appname': cnf.appname.capitalize()},
                 'config': {'catcherror': DisplayController.CATCHERROR}}
        maps = cnf.readuserconfig(maps, update = True)

        DisplayController.CATCHERROR = maps['config']['catcherror']
        kwa.setdefault("title",  maps['theme']["appname"])
        kwa.setdefault("size",   maps['theme']['appsize'])
        return kwa

    def _open(self, viewcls, doc, kwa):
        keys = DpxKeyEvent(self)
        self.topview = viewcls(self, **kwa)
        if hasattr(self.topview.views[0], 'ismain'):
            self.topview.views[0].ismain(self)

        self._configio()
        if doc is None:
            return self
        self._observe(keys)
        self._bokeh(keys, doc)
        self.display.handle('applicationstarted', self.display.emitpolicy.nothing)
        return self

    def _observe(self, keys):
        "Returns the methods for observing user start & stop action delimiters"
        if keys:
            keys.observe(self)
        for i in self.topview.views:
            getattr(i, 'observe', lambda *_: None)(self)

        # now observe all events that should be saved in the config
        self._config_counts = [False]

        @self.display.observe
        def _onstartaction(recursive = None): # pylint: disable=unused-variable
            if recursive is False:
                self._config_counts[0]  = False

        def _onconfig(*_1, **_2):
            self._config_counts[0] = True

        args = self._observeargs()
        assert len(args) % 2 == 0
        for i in range(0, len(args), 2):
            args[i].observe(args[i+1], _onconfig)

        for i in self.theme.values():
            self.theme.observe(i, _onconfig)

        @self.display.observe
        def _onstopaction(recursive = None, **_): # pylint: disable=unused-variable
            if recursive is False:
                self._config_counts, val = [False], self._config_counts[0]
                if val:
                    self.writeuserconfig()

    def _bokeh(self, keys, doc):
        for mdl in orders().dynloads():
            getattr(sys.modules.get(mdl, None), 'document', lambda x: None)(doc)

        roots = getattr(self.topview.views[0], 'addtodoc', lambda *_: None)(self, doc)
        if roots is None:
            return

        theme = self.theme.model("main").theme
        if theme:
            doc.theme = Theme(json = theme)

        while isinstance(roots, (tuple, list)) and len(roots) == 1:
            roots = roots[0]

        if not isinstance(roots, (tuple, list)):
            roots = (roots,)

        keys.addtodoc(self, doc)
        if isinstance(roots, (tuple, list)) and len(roots) == 1:
            doc.add_root(roots[0])
        else:
            mode = self.theme.get('main', 'sizingmode', 'fixed')
            doc.add_root(layout(roots, sizing_mode = mode))

    def _configio(self):
        cnf  = ConfigurationIO(self)
        maps = self._getmaps()

        # 1. write the whole config down
        cnf.writeuserconfig(maps, "defaults",   True,  index = 1)

        # 2. read & write the user-provided config: discards unknown keys
        cnf.writeuserconfig(cnf.readconfig(maps, "userconfig"), "userconfig", False, index = 0)

        # read the config from files:
        self._setmaps(cnf.readuserconfig(maps))

        orders().config(self)

    def _getmaps(self):
        maps = {'theme':  {'appsize': self.APPSIZE, 'appname': self.APPNAME.capitalize()},
                'config': {'catcherror': DisplayController.CATCHERROR}}
        keys = {i for i, j in self.theme.current.items()
                if type(j).__name__.endswith("Config")}
        outs = {f'{"config." if i in keys else "theme."}{i}': j
                for i, j in self.theme.config.items()}
        for i, j in maps.items():
            j.update(outs.pop(i, {}))
        maps.update(outs)
        return maps

    def _setmaps(self, maps):
        for i, j in maps.items():
            if i.startswith('theme.') and i[6:] in self.theme and j:
                self.theme.update(i[6:], **j)
            elif i.startswith('config.') and i[7:] in self.theme and j:
                self.theme.update(i[7:], **j)

    def _observeargs(self):
        raise NotImplementedError()

class SuperController(BaseSuperController):
    """
    Main controller: contains all sub-controllers.
    These share a common dictionnary of handlers
    """
    def __init__(self, view):
        hdl: dict    = dict()
        self.tasks   = TaskController(handlers = hdl)
        super().__init__(view, handlers = hdl)

    def _observe(self, keys):
        "starts the controler"
        super()._observe(keys)
        self.tasks.setup(self)

    def _observeargs(self):
        return (self.tasks, "opentrack",
                self.tasks, "addtask",
                self.tasks, "updatetask",
                self.tasks, "removetask",
                self.tasks, "closetrack")

def createview(main, controls, views):
    "Creates a main view"
    controls = (SuperController,)+tuple(controls)
    views    = (main,)+tuple(views)
    return ConfigurationIO.createview((SuperController,)+controls, views)
