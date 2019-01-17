#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers and toolbar"
from app.launcher  import setup
from app.toolbar   import toolbarview
from .default      import VIEWS, CONTROLS
from .maincontrol  import createview as _createview

def createview(main, controls, views):
    "Creates an app with a toolbar"
    return _createview(toolbarview('taskview.toolbar.BeadToolbar', main), controls, views)

setup(locals(), creator = createview, defaultcontrols = CONTROLS, defaultviews = VIEWS)
