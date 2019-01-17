#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from typing     import Dict, Any

import sys

from tornado.platform.asyncio   import AsyncIOMainLoop
from bokeh.application          import Application
from bokeh.application.handlers import FunctionHandler
from bokeh.server.server        import Server
from bokeh.settings             import settings
from bokeh.resources            import DEFAULT_SERVER_PORT

from utils.logconfig            import getLogger
from .scripting                 import orders
from .maincontrol               import createview as _creator

LOGS        = getLogger(__name__)
CAN_LOAD_JS = "."

class _FunctionHandler(FunctionHandler):
    def __init__(self, view, stop = False):
        self.__gotone        = False
        self.server          = None
        self.stoponnosession = stop
        self.view            = view
        super().__init__(self.__start)

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

    @classmethod
    def serveapplication(cls, view, **kwa):
        "Launches a bokeh server"
        # monkeypatch the js production: it's been done once & saved during compilation
        cls.__monkeypatch_bokeh(view)
        cls.__server_kwargs(kwa)

        fcn                = cls(view)
        server             = Server(Application(fcn), **kwa)
        fcn.server         = server
        server.MainView    = view
        server.appfunction = fcn
        return server

    @classmethod
    def launchflexx(cls, view, **kwa):
        "Launches a bokeh server"
        from webruntime           import launch as _flexxlaunch
        port = kwa.get('port', str(DEFAULT_SERVER_PORT))
        if isinstance(kwa.get('size', ()), list):
            kwa['size'] = tuple(kwa['size'])

        if isinstance(view, Server):
            server = view
        else:
            server = cls.serveapplication(view, **kwa.pop('server', {}), port = port)

        cls.__monkeypatch_flexx(server)
        view.MainControl.FLEXXAPP = _flexxlaunch('http://localhost:{}/'.format(port),
                                                 **kwa)
        return server

    @staticmethod
    def __monkeypatch_flexx(server):
        from webruntime._common         import StreamReader
        def run(self, __old__ = StreamReader.run):
            "Stop the stream reader"
            __old__(self)
            server.stop()
        StreamReader.run = run

    @staticmethod
    def __monkeypatch_bokeh(view):
        from bokeh.core.properties import Seq
        def from_json(self, json, models=None, __old__ = Seq.from_json):
            "parse docstring"
            if isinstance(json, dict):
                json = {int(i): j for i, j in json.items()}
                keys = sorted(json)
                assert keys == list(range(max(json)+1))
                json = [json[i] for i in keys]
            return __old__(self, json, models = models)
        Seq.from_json = from_json

        if CAN_LOAD_JS:
            from utils.gui import storedjavascript
            storedjavascript(CAN_LOAD_JS, view.APPNAME)

        def _stop(self, wait=True, __old__ = Server.stop):
            if not getattr(self, '_stopped', False):
                __old__(self, wait)
            self.io_loop.stop()
        Server.stop = _stop

    @staticmethod
    def __server_kwargs(kwa)-> Dict[str, Any]:
        kwa.setdefault('sign_sessions',        settings.sign_sessions())
        kwa.setdefault('secret_key',           settings.secret_key_bytes())
        kwa.setdefault('generate_session_ids', True)
        kwa.setdefault('use_index',            True)
        kwa.setdefault('redirect_root',        True)
        kwa['port'] = int(kwa.get('port', DEFAULT_SERVER_PORT))
        kwa.pop('runtime', None)
        if isinstance(kwa.get('size', ()), list):
            kwa['size'] = tuple(kwa['size'])
        LOGS.debug("dynamic loads: %s", orders().dynloads())
        for mdl in orders().dynloads():
            getattr(sys.modules.get(mdl, None), 'server', lambda x: None)(kwa)
        return kwa

    def __onloaded(self):
        if self.__gotone is False:
            self.__gotone = True
            LOGS.debug("GUI loaded")

    def __start(self, doc):
        doc.title = self.view.launchkwargs()['title']
        orders().run(self.view, doc, self.__onloaded)

def setup(locs,           #
          creator         = _creator,
          defaultcontrols = tuple(),
          defaultviews    = tuple(),
         ):
    """
    Populates a module with launch and serve functions for a given app context.

    The context is created as follows, say in module `app.mycontext`:

    ```python
    #!/usr/bin/env python3
    # -*- coding: utf-8 -*-
    "Updates app manager so as to deal with controllers"
    from .launcher  import setup

    VIEWS       = ('undo.UndoView', 'view.tasksview.TasksView',)
    CONTROLS    = ('control.taskcontrol.TaskController',
                   'taskstore.control',
                   'undo.UndoController')

    setup(locals(), defaultcontrols = CONTROLS, defaultviews = VIEWS)
    ```

    To launch a `webruntime` window displayng `myview.MyView`:

    ```python
    from app.mycontext import launch
    launch("myview.MyView")
    ```

    See `app.toolbar` for an example which sets-up a toolbar above any view provided
    as a argument.
    """
    def application(main,
                    creator  = creator,
                    controls = defaultcontrols,
                    views    = defaultviews):
        "Creates a main view"
        return creator(main, controls, views)

    def serve(main,
              creator  = creator,
              controls = defaultcontrols,
              views    = defaultviews,
              apponly  = False,
              **kwa):
        "Creates a browser app"
        AsyncIOMainLoop().install()
        app = application(main, creator, controls, views)
        if apponly:
            return app
        return _FunctionHandler.serveapplication(app, **kwa)

    def launch(main,
               creator  = creator,
               controls = defaultcontrols,
               views    = defaultviews,
               apponly  = False,
               **kwa):
        "Creates a desktop app"
        AsyncIOMainLoop().install()
        app = application(main, creator, controls, views)
        if apponly:
            return app
        return _FunctionHandler.launchflexx(app, **app.launchkwargs(**kwa))

    locs.setdefault('application',  application)
    locs.setdefault('serve',        serve)
    locs.setdefault('launch',       launch)
