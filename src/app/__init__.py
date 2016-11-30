#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controllers"
from functools  import wraps

from flexx.webruntime               import launch as _flexxlaunch
from flexx.webruntime.common        import StreamReader
from bokeh.server.server            import Server
from bokeh.application              import Application
from bokeh.application.handlers     import FunctionHandler
from bokeh.command.util             import build_single_handler_application
from bokeh.settings                 import settings

from utils          import MetaMixin
from control        import Controller
from view           import View, BokehView
from view.keypress  import KeyPressManager

def _serverkwargs():
    server_kwargs                         = dict()
    server_kwargs['sign_sessions']        = settings.sign_sessions()
    server_kwargs['secret_key']           = settings.secret_key_bytes()
    server_kwargs['generate_session_ids'] = True
    server_kwargs['use_index']            = True
    server_kwargs['redirect_root']        = True
    return server_kwargs

def _serve(view):
    u"Launches a bokeh server"
    def start(doc):
        u"Starts the application and adds itself to the document"
        self = view() # pylint: disable=no-value-for-parameter
        self.open(doc)
        return self

    return Server(Application(FunctionHandler(start)), **_serverkwargs())

def _launch(view, **kwa):
    u"Launches a bokeh server"
    server     = _serve(view)
    old        = StreamReader.run
    def run(self):
        u"Stop the stream reader"
        old(self)
        server.stop()
    StreamReader.run = run

    rtime                  = _flexxlaunch('http://localhost:5006/', **kwa)
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

    def __init__(self):
        u"sets up the controller, then initializes the view"
        ctrl = MainControl(handlers = dict(), topview = self)
        keys = KeyPressManager(ctrl = ctrl)
        main.__init__(self, ctrl = ctrl, keys = keys)

    return type('Main', (main,)+views,
                dict(__doc__     = u"The main view",
                     MainControl = MainControl,
                     __init__    = __init__))

def setup(locs,
          mainview        = None,
          creator         = lambda _: _,
          defaultcontrols = tuple(),
          defaultviews    = tuple()
         ):
    u"Sets up launch and serve functions for a given app context"

    classes = set(cls for cls in locs.values() if isinstance(cls, type))
    classes.difference_update((Controller, View))
    if defaultcontrols is all:
        defaultcontrols = tuple(i for i in classes if issubclass(i, Controller))

    if defaultviews is all:
        defaultviews = tuple(i for i in classes
                             if (issubclass(i, View)
                                 and not issubclass(i, BokehView)))

    def serve(main     = mainview,
              controls = defaultcontrols,
              views    = defaultviews,
              creator  = creator,
              **kwa):
        u"Creates a browser app"
        return _serve(_create(creator(main), controls, views), **kwa)

    def launch(main     = mainview,
               controls = defaultcontrols,
               views    = defaultviews,
               creator  = creator,
               **kwa):
        u"Creates a desktop app"
        kwa.setdefault("title", 'track analysis')
        kwa.setdefault("size",  (1000, 1000))
        return _launch(_create(creator(main), controls, views), **kwa)

    locs.setdefault('serve',   serve)
    locs.setdefault('launch',  launch)

setup(locals())
