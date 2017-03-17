#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from typing     import TYPE_CHECKING
from functools  import wraps
from pathlib    import Path

import appdirs

from flexx.webruntime           import launch as _flexxlaunch
from flexx.webruntime.common    import StreamReader
from bokeh.server.server        import Server
from bokeh.application          import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.command.util         import build_single_handler_application
from bokeh.settings             import settings
from bokeh.layouts              import layout

from utils         import getlocals
from utils.gui     import MetaMixin
from control       import Controller
from view          import View, BokehView
from view.keypress import KeyPressManager
import view.toolbar as toolbars

def _serverkwargs(kwa):
    server_kwargs                         = dict(kwa)
    server_kwargs['sign_sessions']        = settings.sign_sessions()
    server_kwargs['secret_key']           = settings.secret_key_bytes()
    server_kwargs['generate_session_ids'] = True
    server_kwargs['use_index']            = True
    server_kwargs['redirect_root']        = True
    return server_kwargs

def _title(view) -> str:
    appname   = getattr(view.MainControl, 'APPNAME', 'track analysis')
    return appname.capitalize()

def _serve(view, **kwa):
    "Launches a bokeh server"
    def start(doc):
        "Starts the application and adds itself to the document"
        doc.title = _title(view)
        return view.open(doc)

    server = Server(Application(FunctionHandler(start)), **_serverkwargs(kwa))
    server.MainView = view
    return server

def _launch(view, **kwa):
    "Launches a bokeh server"
    if isinstance(view, Server):
        server = view
    else:
        server = _serve(view, **kwa.pop('server', {}))

    def run(self, __old__ = StreamReader.run):
        "Stop the stream reader"
        __old__(self)
        if not getattr(server, '_stopped', False):
            server.stop()
        server.io_loop.stop()
    StreamReader.run = run

    rtime = _flexxlaunch('http://localhost:5006/', **kwa)
    def close(self, __old__ = view.MainControl.close):
        "closes the application"
        top, self.topview = self.topview, None
        if top is not None:
            __old__(self)
            top.close()
            rtime.close()
    view.MainControl.ISAPP = True
    view.MainControl.close = close
    return server

def _create(main, controls, views): # pylint: disable=unused-argument
    "Creates a main view"

    class Main(*(main,)+views):
        "The main view"
        class MainControl(metaclass   = MetaMixin,
                          mixins      = controls,
                          selectfirst = True):
            """
            Main controller: contains all sub-controllers.
            These share a common dictionnary of handlers
            """
            ISAPP    = False
            APPNAME  = next((i.APPNAME for i in (main,)+views if hasattr(i, 'APPNAME')),
                            'Track Analysis')
            def __init__(self, **kwa):
                self.topview = kwa['topview']

            if TYPE_CHECKING:
                def _yieldovermixins(self, *_1, **_2):
                    pass
                def _callmixins(self, *_1, **_2):
                    pass

            def __undos__(self):
                "yields all undoable user actions"
                yield from self._yieldovermixins('__undos__')

            @classmethod
            def configpath(cls, version) -> Path:
                "returns the path to the config file"
                name = cls.APPNAME.replace(' ', '_').lower()
                path = Path(appdirs.user_config_dir('depixus', 'depixus', name+"/"+version))
                return path/'config.txt'

            def readconfig(self):
                "writes the config"
                self._callmixins("readconfig", self.configpath)

            def writeconfig(self):
                "writes the config"
                self._callmixins("writeconfig", self.configpath)

            def close(self):
                "remove controller"
                self.writeconfig()
                self._callmixins("close")

        def __init__(self):
            "sets up the controller, then initializes the view"
            ctrl = self.MainControl(handlers = dict(), topview = self)
            keys = KeyPressManager(ctrl = ctrl)
            main.__init__(self, ctrl = ctrl, keys = keys)

            ctrl.readconfig()
            main.observe(self)
            for cls in views:
                cls.observe(self)

    return Main

def setup(locs            = None, # pylint: disable=too-many-arguments
          mainview        = None,
          creator         = lambda _: _,
          defaultcontrols = tuple(),
          defaultviews    = tuple(),
          decorate        = lambda x: x
         ):
    "Sets up launch and serve functions for a given app context"
    if locs is None:
        locs = getlocals(1)

    @decorate
    def application(main     = mainview,
                    controls = defaultcontrols,
                    views    = defaultviews,
                    creator  = creator):
        "Creates a main view"
        def _get(string):
            if isinstance(string, str):
                mod  = string[:string.rfind('.')]
                attr = string[string.rfind('.')+1:]
                return getattr(__import__(mod, fromlist = (attr,)), attr)
            return string

        classes = set(cls for cls in locs.values() if isinstance(cls, type))
        classes.difference_update((Controller, View))
        if controls in (all, Ellipsis):
            controls = tuple(i for i in classes if issubclass(i, Controller))
        else:
            controls = tuple(_get(i) for i in controls)

        if views in (all, Ellipsis):
            views = tuple(i for i in classes
                          if (issubclass(i, View)
                              and not issubclass(i, BokehView)))
        else:
            views = tuple(_get(i) for i in views)

        return _create(creator(main), controls, views)

    @decorate
    def serve(main     = mainview,
              controls = defaultcontrols,
              views    = defaultviews,
              creator  = creator,
              **kwa):
        "Creates a browser app"
        return _serve(application(main, controls, views, creator), **kwa)

    @decorate
    def launch(main     = mainview,
               controls = defaultcontrols,
               views    = defaultviews,
               creator  = creator,
               **kwa):
        "Creates a desktop app"
        app = application(main, controls, views, creator)
        kwa.setdefault("title", _title(app))
        kwa.setdefault("size",  (1000, 1000))
        return _launch(app, **kwa)

    locs.setdefault('serve',   serve)
    locs.setdefault('launch',  launch)

class WithToolbar:
    "Creates an app with a toolbar"
    def __init__(self, tbar):
        self.tbar = tbar

    def __call__(self, main):
        tbar = self.tbar
        class ViewWithToolbar(BokehView):
            "A view with the toolbar on top"
            APPNAME = getattr(main, 'APPNAME', main.__name__.lower().replace('view', ''))
            def __init__(self, **kwa):
                self._bar      = tbar(**kwa)
                self._mainview = main(**kwa)
                super().__init__(**kwa)

            def close(self):
                "remove controller"
                super().close()
                self._bar.close()
                self._mainview.close()

            def getroots(self, doc):
                "adds items to doc"
                children = [self._bar.getroots(doc), self._mainview.getroots(doc)]
                return layout(children, sizing_mode = 'scale_width'),

        return ViewWithToolbar

VIEWS       = ('undo.UndoView', 'view.globalsview.GlobalsView',)
CONTROLS    = ('control.taskcontrol.TaskController',
               'control.globalscontrol.GlobalsController',
               'undo.UndoController')

setup()

class Defaults:
    "Empty app"
    setup(defaultcontrols = CONTROLS, defaultviews = VIEWS)

class ToolBar:
    "App with a toolbar"
    setup(creator         = WithToolbar(toolbars.ToolBar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.ToolBar",))

class BeadsToolBar:
    "App with a toolbar containing a bead spinner"
    setup(creator         = WithToolbar(toolbars.BeadToolBar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.BeadToolBar",))
