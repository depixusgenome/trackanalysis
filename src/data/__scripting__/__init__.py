#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkey patches the Track & TrackViews classes as well as provide dictionnaries
for collecting tracks and experiments.
"""
from typing         import List
from .tracksdict    import TracksDict
from .track         import Track
from .trackio       import * # pylint: disable=redefined-builtin,wildcard-import
from .trackviews    import * # pylint: disable=redefined-builtin,wildcard-import
from .dataframe     import * # pylint: disable=redefined-builtin,wildcard-import
__all__: List[str] = ['TracksDict', 'Track']
