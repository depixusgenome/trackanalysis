#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controllers"
from functools  import wraps
from flexx      import app, ui

from utils      import MetaMixin
from control    import Controller
from view       import View, FlexxView

def _create(main, controls, views): # pylint: disable=unused-argument
    u"Creates a main view"
    def init(self):
        u"sets up the controller, then initializes the view"
        main.init(self)
        ctrl         = self.MainControl(handlers = dict())
        ctrl.topview = self
        self.open(ctrl)

    class MainControl(metaclass = MetaMixin,
                      mixins    = controls):
        u"""
        Main controller: contains all sub-controllers.
        These share a common dictionnary of handlers
        """
        def __init__(self, **_):
            self.topview = None # type: Optional[FlexxView]

        def close(self):
            u"closes the application"
            main, self.topview = self.topview, None
            main.close()

    cls = type('Main', (main,)+views,
               dict(__doc__     = u"The main view",
                    MainControl = MainControl,
                    init        = init))
    return cls

def setup(locs,
          mainview        = None,
          creator         = lambda _: _,
          defaultcontrols = tuple(),
          defaultviews    = tuple()
         ):
    u"Sets up launch and serve functions for a given app context"

    classes = set(cls for cls in locs.values() if isinstance(cls, type))
    classes.difference_update((Controller, View, FlexxView, ui.Widget))
    if defaultcontrols is all:
        defaultcontrols = tuple(i for i in classes if issubclass(i, Controller))

    if defaultviews is all:
        defaultviews = tuple(i for i in classes
                             if (issubclass(i, View)
                                 and not issubclass(i, ui.Widget)))

    def serve(main     = mainview,
              controls = defaultcontrols,
              views    = defaultviews,
              creator  = creator,
              **kwa):
        u"Creates a browser app"
        return app.serve(_create(creator(main), controls, views), **kwa)

    def launch(main     = mainview,
               controls = defaultcontrols,
               views    = defaultviews,
               creator  = creator,
               **kwa):
        u"Creates a desktop app"
        cls = _create(creator(main), controls, views)

        # next is to correct a bug in flexx
        old = app.session.Session.close
        @wraps(old)
        def close(self):
            u"closes app"
            old(self)
            app.call_later(0, app.stop)
        app.session.Session.close = close

        kwa.setdefault("title", 'track analysis')
        kwa.setdefault("size",  (1000, 1000))

        locs['TOPVIEW'] = app.launch(cls, **kwa)
        return locs['TOPVIEW']

    def start(path = None, script = None):
        u"starts the server"
        if locs['TOPVIEW'] is not None and (path, script) != (None, None):
            app.call_later(1, lambda: locs['TOPVIEW'].startup(path, script))
        app.start()

    def run(path = None, script = None):
        u"starts the server"
        if locs['TOPVIEW'] is not None and (path, script) != (None, None):
            app.call_later(1, lambda: locs['TOPVIEW'].startup(path, script))
        app.run()

    locs.setdefault('TOPVIEW', None)
    locs.setdefault('serve',  serve)
    locs.setdefault('launch', launch)
    locs.setdefault('start',  start)
    locs.setdefault('run',  run)

setup(locals())
