#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controllers"
from   functools      import wraps

import flexx.app as app

from utils          import MetaMixin
from control.event  import Controller
from view           import View

def _create(main, controls, views): # pylint: disable=unused-argument
    u"Creates a main view"
    def init(self):
        u"sets up the controller, then initializes the view"
        main.init(self)
        self.observe    (self.MainControl())
        self.addKeyPress(quit = self.close)

    def close(self):
        u"closes the application"
        self.popKeyPress(all)
        self.unobserve()
        self.session.close()

    class MainControl(metaclass = MetaMixin,
                      mixins    = controls,
                      shared    = ('_handlers',)):
        u"""
        Main controller: contains all sub-controllers.
        These share a common dictionnary of handlers
        """

    cls = type('Main', (main,)+views,
               dict(__doc__     = u"The main view",
                    MainControl = MainControl,
                    close       = close,
                    init        = init))
    return cls

def setup(locs,
          mainview        = None,
          defaultcontrols = tuple(),
          defaultviews    = tuple()
         ):
    u"Sets up launch and serve functions for a given app context"

    get = lambda tpe: tuple(cls for cls in locs.values()
                            if isinstance(cls, type) and issubclass(cls, tpe))
    if defaultcontrols is all:
        defaultcontrols = get(Controller)

    if defaultviews is all:
        defaultviews = get(View)

    def serve(main     = mainview,
              controls = defaultcontrols,
              views    = defaultviews,
              **kwa):
        u"Creates a browser app"
        kwa.setdefault("title", 'track analysis')
        return app.serve(_create(main, controls, views), **kwa)

    def launch(main     = mainview,
               controls = defaultcontrols,
               views    = defaultviews,
               **kwa):
        u"Creates a desktop app"
        cls = _create(main, controls, views)

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
