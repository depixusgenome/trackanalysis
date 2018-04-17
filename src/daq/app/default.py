#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from typing        import List
from app.launcher  import setup
from .maincontrol  import createview

VIEWS               = ['daq.server.dataviews.DAQFoVServerView',
                       'daq.server.dataviews.DAQBeadsServerView']
CONTROLS: List[str] = []

setup(locals(), defaultcontrols = CONTROLS, defaultviews = VIEWS, creator = createview)
