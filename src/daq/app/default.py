#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updates app manager so as to deal with controllers"
from app.launcher  import setup
from .maincontrol  import createview

VIEWS       = ()
CONTROLS    = ('daq.control',)
setup(locals(), defaultcontrols = CONTROLS, defaultviews = VIEWS, creator = createview)
