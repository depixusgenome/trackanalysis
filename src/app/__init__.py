#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controllers"
from functools  import wraps

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

def _serve(view, **kwa):
    u"Launches a bokeh server"
    def start(doc):
        u"Starts the application and adds itself to the document"
        return view.open(doc)

    server = Server(Application(FunctionHandler(start)), **_serverkwargs(kwa))
    server.MainView = view
    return server

def _launch(view, **kwa):
    u"Launches a bokeh server"
    if isinstance(view, Server):
        server = view
    else:
        server = _serve(view, **kwa.pop('server', {}))

    old        = StreamReader.run
    def run(self):
        u"Stop the stream reader"
        old(self)
        if not getattr(server, '_stopped', False):
            server.stop()
        server.io_loop.stop()
    StreamReader.run = run

    rtime = _flexxlaunch('http://localhost:5006/', **kwa)
    def close(self):
        u"closes the application"
        top, self.topview = self.topview, None
        if top is not None:
            self._callmixins('close') # pylint: disable=protected-access
            top.close()
            rtime.close()
    view.MainControl.ISAPP = True
    view.MainControl.close = close
    return server

def _create(main, controls, views): # pylint: disable=unused-argument
    u"Creates a main view"
    class MainControl(metaclass   = MetaMixin,
                      mixins      = controls,
                      selectfirst = True):
        u"""
        Main controller: contains all sub-controllers.
        These share a common dictionnary of handlers
        """
        ISAPP = False
        def __init__(self, **kwa):
            self.topview = kwa['topview']

        def __undos__(self):
            u"yields all undoable user actions"
            yield from self._yieldovermixins('__undos__') # pylint: disable=no-member

    def __init__(self):
        u"sets up the controller, then initializes the view"
        ctrl = MainControl(handlers = dict(), topview = self)
        keys = KeyPressManager(ctrl = ctrl)
        main.__init__(self, ctrl = ctrl, keys = keys)

    return type('Main', (main,)+views,
                dict(__doc__     = u"The main view",
                     MainControl = MainControl,
                     __init__    = __init__))

def setup(locs            = None, # pylint: disable=too-many-arguments
          mainview        = None,
          creator         = lambda _: _,
          defaultcontrols = tuple(),
          defaultviews    = tuple(),
          decorate        = lambda x: x
         ):
    u"Sets up launch and serve functions for a given app context"
    if locs is None:
        locs = getlocals(1)

    @decorate
    def application(main     = mainview,
                    controls = defaultcontrols,
                    views    = defaultviews,
                    creator  = creator):
        u"Creates a main view"
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
        u"Creates a browser app"
        return _serve(application(main, controls, views, creator), **kwa)

    @decorate
    def launch(main     = mainview,
               controls = defaultcontrols,
               views    = defaultviews,
               creator  = creator,
               **kwa):
        u"Creates a desktop app"
        kwa.setdefault("title", 'track analysis')
        kwa.setdefault("size",  (1000, 1000))
        return _launch(application(main, controls, views, creator), **kwa)

    locs.setdefault('serve',   serve)
    locs.setdefault('launch',  launch)

class WithToolbar:
    u"Creates an app with a toolbar"
    def __init__(self, tbar):
        self.tbar = tbar

    def __call__(self, main):
        tbar = self.tbar
        class ViewWithToolbar(BokehView):
            u"A view with the toolbar on top"
            def __init__(self, **kwa):
                self._bar      = tbar(**kwa)
                self._mainview = main(**kwa)
                super().__init__(**kwa)

            def close(self):
                u"remove controller"
                super().close()
                self._bar.close()
                self._mainview.close()

            def getroots(self):
                u"adds items to doc"
                children = [self._bar.getroots(), self._mainview.getroots()]
                return layout(children, sizing_mode = 'scale_width'),

        return ViewWithToolbar

VIEWS       = ('undo.UndoView', 'view.globalsview.GlobalsView',)
CONTROLS    = ('control.taskcontrol.TaskController',
               'control.globalscontrol.GlobalsController',
               'undo.UndoController')

setup()

class Defaults:
    u"Empty app"
    setup(defaultcontrols = CONTROLS, defaultviews = VIEWS)

class ToolBar:
    u"App with a toolbar"
    setup(creator         = WithToolbar(toolbars.ToolBar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.ToolBar",))

class BeadsToolBar:
    u"App with a toolbar containing a bead spinner"
    setup(creator         = WithToolbar(toolbars.BeadToolBar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.BeadToolBar",))
