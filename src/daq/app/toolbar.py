#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers and toolbar"
from app.launcher import setup
from app.toolbar  import createview as _createview
from ..toolbar    import DAQToolbar

def createview(main, controls, views):
    "Creates an app with a toolbar"
    return _createview(main, controls, views, tbar = DAQToolbar)

VIEWS       = ('daq.serverview',)
CONTROLS    = ()

setup(locals(), creator = createview, defaultcontrols = CONTROLS, defaultviews = VIEWS)
