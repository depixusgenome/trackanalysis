#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from typing     import TYPE_CHECKING, List, Callable, Tuple # pylint: disable=unused-import
from pathlib    import Path

import sys
import appdirs

from flexx.webruntime           import launch as _flexxlaunch
from flexx.webruntime.common    import StreamReader
from bokeh.server.server        import Server
from bokeh.application          import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.settings             import settings
from bokeh.layouts              import layout
from bokeh.resources            import DEFAULT_SERVER_PORT

from utils.logconfig            import getLogger, logToFile
from utils                      import getlocals
from utils.gui                  import MetaMixin # pylint: disable=unused-import
from control                    import Controller
from view                       import View, BokehView
from view.keypress              import KeyPressManager
import view.toolbar as toolbars

from .scripting                 import INITIAL_ORDERS

LOGS           = getLogger(__name__)
DEFAULT_CONFIG = lambda x: None
DYN_LOADS      = ('modaldialog', 'view') # type: Tuple[str,...]

def _serverkwargs(kwa):
    kwargs                         = dict(kwa)
    kwargs['sign_sessions']        = settings.sign_sessions()
    kwargs['secret_key']           = settings.secret_key_bytes()
    kwargs['generate_session_ids'] = True
    kwargs['use_index']            = True
    kwargs['redirect_root']        = True
    for mdl in DYN_LOADS:
        getattr(sys.modules.get(mdl, None), 'server', lambda x: None)(kwargs)
    return kwargs

def _title(view) -> str:
    appname   = getattr(view.MainControl, 'APPNAME', 'track analysis')
    return appname.capitalize()

def _stop(self, wait=True, __old__ = Server.stop):
    if not getattr(self, '_stopped', False):
        __old__(self, wait)
    self.io_loop.stop()
Server.stop = _stop
del _stop

class _FunctionHandler(FunctionHandler):
    def __init__(self, view, stop = False):
        self.__gotone        = False
        self.server          = None
        self.stoponnosession = stop

        def _onloaded():
            if self.__gotone is False:
                self.__gotone = True
                LOGS.debug("GUI loaded")

        def _start(doc):
            doc.title = _title(view)
            INITIAL_ORDERS.run(view, doc, _onloaded)
        super().__init__(_start)

    def on_session_created(self, session_context):
        LOGS.debug('started session')

    def on_session_destroyed(self, session_context):
        LOGS.debug('destroyed session')
        if not self.__gotone:
            return

        if self.server is not None and self.stoponnosession:
            server, self.server = self.server, None
            if len(server.get_sessions()) == 0:
                LOGS.info('no more sessions -> stopping server')
                server.stop()

def _monkeypatch(view):
    output = view.MainControl.APPNAME.lower() + '.js'
    if Path(output).exists():
        LOGS.debug('monkeypatching bokeh compiler with '+output)
        def _bundle():
            return ''.join(open(output))
        import bokeh.embed      as embed
        embed.bundle_all_models = _bundle

def _serve(view, **kwa):
    "Launches a bokeh server"
    fcn    = _FunctionHandler(view)
    _monkeypatch(view)
    server = Server(Application(fcn), **_serverkwargs(kwa))
    fcn.server = server
    server.MainView    = view
    server.appfunction = fcn
    return server

def _launch(view, **kwa):
    "Launches a bokeh server"
    if isinstance(view, Server):
        server = view
    else:
        skwa = kwa.pop('server', {})
        skwa.setdefault('port', kwa.get('port', DEFAULT_SERVER_PORT))
        server = _serve(view, **skwa)

    def run(self, __old__ = StreamReader.run):
        "Stop the stream reader"
        __old__(self)
        server.stop()
    StreamReader.run = run

    port  = kwa.get('port', str(DEFAULT_SERVER_PORT))
    rtime = _flexxlaunch('http://localhost:{}/'.format(port), **kwa)
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
            def configpath(cls, version, stem = None) -> Path:
                "returns the path to the config file"
                fname = ('autosave' if stem is None else stem)+'.txt'
                return cls.apppath()/str(version)/fname

            def readconfig(self):
                """
                reads the config: first the stuff saved automatically, then
                anything the user wishes to impose.
                """
                ctrl = self.globalscontroller # pylint: disable=no-member
                ctrl.readconfig(self.configpath)
                ctrl.readconfig(self.configpath, lambda i: self.configpath(i, 'userconfig'))
                DEFAULT_CONFIG(self)

            def writeconfig(self, name = None, saveall = False, **kwa):
                "writes the config"
                kwa['saveall'] = saveall
                ctrl = self.globalscontroller # pylint: disable=no-member
                ctrl.writeconfig(lambda i: self.configpath(i, name), **kwa)

            def setup(self):
                "writes the config"
                self._callmixins("setup", self)

            def close(self):
                "remove controller"
                self.writeconfig()
                self._callmixins("close")

            @classmethod
            def apppath(cls) -> Path:
                "returns the path to local appdata directory"
                name = cls.APPNAME.replace(' ', '_').lower()
                return Path(appdirs.user_config_dir('depixus', 'depixus', name))

        def __init__(self):
            "sets up the controller, then initializes the view"

            ctrl = self.MainControl(handlers = dict(), topview = self)
            keys = KeyPressManager(ctrl = ctrl)
            main.__init__(self, ctrl = ctrl, keys = keys)
            main.ismain(self)

            ctrl.writeconfig('defaults',   index = 1, saveall   = True)
            ctrl.writeconfig('userconfig', index = 0, overwrite = False)
            ctrl.readconfig()
            ctrl.setup()
            main.observe(self)
            for cls in views:
                cls.observe(self)

        def addtodoc(self, doc):
            "Adds one's self to doc"
            for mdl in DYN_LOADS:
                getattr(sys.modules.get(mdl, None), 'document', lambda x: None)(doc)
            super().addtodoc(doc)

    logToFile(str(Main.MainControl.apppath()/"logs.txt"))
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
                if attr[0] != attr[0].upper():
                    __import__(string)
                    return None

                return getattr(__import__(mod, fromlist = (attr,)), attr)
            return string

        classes = set(cls for cls in locs.values() if isinstance(cls, type))
        classes.difference_update((Controller, View))
        if controls in (all, Ellipsis):
            controls = tuple(i for i in classes if issubclass(i, Controller))
        else:
            controls = tuple(_get(i) for i in controls if _get(i) is not None)

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
              apponly  = False,
              **kwa):
        "Creates a browser app"
        app = application(main, controls, views, creator)
        if apponly:
            return app
        return _serve(app, **kwa)

    @decorate
    def launch(main     = mainview,
               controls = defaultcontrols,
               views    = defaultviews,
               creator  = creator,
               apponly  = False,
               **kwa):
        "Creates a desktop app"
        app = application(main, controls, views, creator)
        if apponly:
            return app
        kwa.setdefault("title", _title(app))
        kwa.setdefault("size",  (1200, 1000))
        return _launch(app, **kwa)

    locs.setdefault('application', application)
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

            def ismain(self):
                "sets-up the main view as main"
                self._mainview.ismain()

            def close(self):
                "remove controller"
                super().close()
                self._bar.close()
                self._mainview.close()

            def getroots(self, doc):
                "adds items to doc"
                children = [self._bar.getroots(doc), self._mainview.getroots(doc)]
                if self._ctrl.getGlobal('css').responsive.get():
                    return layout(children, responsive = True),

                mode = self._ctrl.getGlobal('css').sizing_mode.get()
                return layout(children, sizing_mode = mode),

        return ViewWithToolbar

VIEWS       = ('undo.UndoView', 'view.globalsview.GlobalsView',)
CONTROLS    = ('control.taskcontrol.TaskController',
               'control.globalscontrol.GlobalsController',
               'anastore.control',
               'undo.UndoController')

setup(locals())

class Defaults:
    "Empty app"
    setup(locals(), defaultcontrols = CONTROLS, defaultviews = VIEWS)

class BeadToolbar:
    "App with a toolbar"
    setup(locals(),
          creator         = WithToolbar(toolbars.BeadToolbar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.BeadToolbar",))
