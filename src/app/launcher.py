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
from bokeh.model                import Model
import bokeh.core.properties as props


from utils.logconfig            import getLogger
from utils                      import getlocals
from utils.gui                  import MetaMixin
from control                    import Controller
from view                       import View, BokehView
from view.keypress              import KeyPressManager
import view.toolbar as toolbars

LOGS           = getLogger(__name__)
DEFAULT_CONFIG = lambda x: None
INITIAL_ORDERS = []     # type: List[Callable]
DYN_LOADS      = ('modaldialog',) # type: Tuple[str,...]

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

class DpxLoaded(Model):
    """
    This starts tests once flexx/browser window has finished loading
    """
    __implementation__ = """
        import *        as $    from "jquery"
        import *        as p    from "core/properties"
        import {Model}          from "model"
        import {BokehView} from "core/bokeh_view"

        export class DpxLoadedView extends BokehView

        export class DpxLoaded extends Model
            default_view: DpxLoadedView
            type: "DpxLoaded"
            constructor : (attributes, options) ->
                super(attributes, options)
                $((e) => @done = 1)
            @define {
                done:  [p.Number, 0]
            }
                         """
    done = props.Int(0)

class _FunctionHandler(FunctionHandler):
    def __init__(self, view, stop = False):
        self.__view          = None
        self.__gotone        = False
        self.server          = None
        self.stoponnosession = stop

        def start(doc):
            "Starts the application and adds itself to the document"
            doc.title   = _title(view)
            self.__view = view.open(doc)

            lst = list(INITIAL_ORDERS)
            if len(lst):
                def _cmd():
                    if len(lst):
                        with self.__view.action:
                            lst.pop(0)(getattr(self.__view, '_ctrl'))
                        doc.add_next_tick_callback(_cmd)

                loaded = DpxLoaded()
                doc.add_root(loaded)
                loaded.on_change('done', lambda attr, old, new: _cmd())
        super().__init__(start)

    def on_session_created(self, session_context):
        LOGS.debug('started session')
        self.__gotone = True

    def on_session_destroyed(self, session_context):
        LOGS.debug('destroyed session')
        if not self.__gotone:
            return

        if self.server is not None and self.stoponnosession:
            server, self.server = self.server, None
            if len(server.get_sessions()) == 0:
                LOGS.info('no more sessions -> stopping server')
                server.stop()

def _serve(view, **kwa):
    "Launches a bokeh server"
    fcn    = _FunctionHandler(view)
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
        server = _serve(view, **kwa.pop('server', {}))

    def run(self, __old__ = StreamReader.run):
        "Stop the stream reader"
        __old__(self)
        server.stop()
    StreamReader.run = run

    rtime = _flexxlaunch('http://localhost:{}/'.format(kwa.get('port', '5006')), **kwa)
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
                name = cls.APPNAME.replace(' ', '_').lower()
                path = Path(appdirs.user_config_dir('depixus', 'depixus', name+"/"+version))
                return path/(('autosave' if stem is None else stem)+'.txt')

            def readconfig(self):
                """
                reads the config: first the stuff saved automatically, then
                anything the user wishes to impose.
                """
                self._callmixins("readconfig", self.configpath)
                self._callmixins("readconfig", lambda i: self.configpath(i, 'userconfig'))
                DEFAULT_CONFIG(self)

            def writeconfig(self, name = None, **kwa):
                "writes the config"
                self._callmixins("writeconfig", lambda i: self.configpath(i, name), **kwa)

            def setup(self):
                "writes the config"
                self._callmixins("setup", self)

            def close(self):
                "remove controller"
                self.writeconfig()
                self._callmixins("close")

        def __init__(self):
            "sets up the controller, then initializes the view"
            ctrl = self.MainControl(handlers = dict(), topview = self)
            keys = KeyPressManager(ctrl = ctrl)
            main.__init__(self, ctrl = ctrl, keys = keys)
            main.ismain(self)

            ctrl.writeconfig('defaults',   index = 1)
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
                else:
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

class ToolBar:
    "App with a toolbar"
    setup(locals(), creator         = WithToolbar(toolbars.ToolBar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.ToolBar",))

class BeadToolBar:
    "App with a toolbar containing a bead spinner"
    setup(locals(), creator         = WithToolbar(toolbars.BeadToolBar),
          defaultcontrols = CONTROLS,
          defaultviews    = VIEWS+("view.toolbar.BeadToolBar",))
