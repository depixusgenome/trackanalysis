#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controllers"
import flexx.app as app

from control.event  import Controller
from view           import View

def _run(main, controls, views, fcn):
    u"Creates a main view"
    def init(self):
        u"sets up the controller, then initializes the view"
        main.init(self)
        self.setCtrl(self.MainControl())

    cls = type('Main', (main,)+views,
               dict(__doc__     = u"The main view",
                    MainControl = type('MainControl', controls, dict()),
                    init        = init))
    return fcn(cls)

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

    def serve(main = mainview, controls = defaultcontrols, views = defaultviews):
        u"Creates a browser app"
        return _run(main, controls, views, app.serve)

    def launch(main = mainview, controls = defaultcontrols, views = defaultviews):
        u"Creates a desktop app"
        return _run(main, controls, views, app.launch)

    locs.setdefault('serve',  serve)
    locs.setdefault('launch', launch)
    locs.setdefault('start',  app.start)

setup(locals())
