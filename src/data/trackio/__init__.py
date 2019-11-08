#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=arguments-differ
"Loading and save tracks"
from ._base     import PATHTYPE, PATHTYPES, TrackIO, TrackIOError
from ._pickle   import PickleIO, savetrack
from ._legacy   import LegacyTrackIO
from ._legacygr import LegacyGRFilesIO
from ._muwells  import MuWellsFilesIO
from ._handler  import Handler, checkpath, opentrack, instrumenttype, instrumentinfo
