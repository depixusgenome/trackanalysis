#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers and toolbar"
from app.launcher import setup
from app.toolbar  import toolbarview
from .maincontrol import createview as _createview

VIEWS       = ('daq.serverview.DAQFoVServerView',
               'daq.serverview.DAQBeadsServerView',
              )#'daq.serverview.DAQAdminView')
CONTROLS    = ()

def createview(main, controls, views):
    "Creates an app with a toolbar"
    return _createview(toolbarview('daq.toolbar.DAQToolbar', main), controls, views)

setup(locals(), creator = createview, defaultcontrols = CONTROLS, defaultviews = VIEWS)
