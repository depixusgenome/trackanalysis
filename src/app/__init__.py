#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controllers"
from   functools      import wraps

import flexx.app as app

from utils          import MetaMixin
from control.event  import Controller
from view           import View, FlexxView

def _create(main, controls, views): # pylint: disable=unused-argument
    u"Creates a main view"
    def init(self):
        u"sets up the controller, then initializes the view"
        main.init(self)
        ctrl         = self.MainControl()
        ctrl.topview = self

        self.observe    (ctrl)
        self.addKeyPress(quit = self.close)

    class MainControl(metaclass = MetaMixin,
                      mixins    = controls,
                      shared    = ('_handlers',)):
        u"""
        Main controller: contains all sub-controllers.
        These share a common dictionnary of handlers
        """
        def __init__(self):
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
    classes.difference_update((Controller, View, FlexxView))
    if defaultcontrols is all:
        defaultcontrols = tuple(i for i in classes if issubclass(i, Controller))

    if defaultviews is all:
        defaultviews = tuple(i for i in classes
                             if (issubclass(i, View)
                                 and not issubclass(i, FlexxView)))

    def serve(main     = mainview,
              controls = defaultcontrols,
              views    = defaultviews,
              creator  = creator,
              **kwa):
        u"Creates a browser app"
        kwa.setdefault("title", 'track analysis')
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
        return app.launch(cls, **kwa)

    locs.setdefault('serve',  serve)
    locs.setdefault('launch', launch)
    locs.setdefault('start',  app.start)

setup(locals())
