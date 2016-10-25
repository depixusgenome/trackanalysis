#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Updates app manager so as to deal with controlers"
import flexx.app as app

from control.event  import Controler
from view           import View

def mainview(view, controls):
    u"Creates a main view"
    return type(view.__name__, (view,),
                dict(MainControl = type('MainControl', controls, dict())))

def setup(locs,
          defaultview     = None,
          defaultcontrols = tuple()
         ):
    u"Sets up launch and serve functions for a given app context"

    if defaultcontrols is all:
        defaultcontrols = tuple(cls for cls in locs.values()
                                if issubclass(cls, Controler))
    def serve(view = defaultview, *controls):
        u"Creates a browser app"
        if len(controls) == 0:
            controls = defaultcontrols
        return app.serve(mainview(view, controls))

    def launch(view = defaultview, *controls, **kwargs):
        u"Creates a desktop app"
        if len(controls) == 0:
            controls = defaultcontrols
        return app.launch(mainview(view, controls), **kwargs)

    locs.setdefault('serve',  serve)
    locs.setdefault('launch', launch)

setup(locals())
