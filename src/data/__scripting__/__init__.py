#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track & TrackViews classes as well as provide dictionnaries
for collecting tracks and experiments.
"""
# pylint: disable=wildcard-import
from .tracksdict            import *
from .track                 import *
from .trackviews            import * # pylint: disable=redefined-builtin
