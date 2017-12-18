#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-import,wildcard-import,ungrouped-imports
"""
Used for scripting: something similar to matplotlib's pyplot.

We add some methods and change the default behaviour:

    * Track:

        * *__init__* takes *path* as it's first positional argument
        * an *events* property is added
        * a *rawprecision* method is added

    * Beads, Cycles:

        * can filter their output using *withfilter*

    * Beads, Cycles, Events:

        * *withcopy(True)* is called in the *__init__* by default
        * a *rawprecision* method is added
        * *with...* methods return an updated copy
"""
import version
from   utils.scripting              import *
import utils.scripting              as     _scripting

from   utils.logconfig              import getLogger
from   eventdetection.processor     import ExtremumAlignmentTask, EventDetectionTask
from   peakfinding.processor        import PeakSelectorTask
import sequences

_scripting.importlibs(locals(),
                      "signalfilter", "scripting.datadump",
                      *(f"{i}.__scripting__" for i in
                        ("model", "app", "data", "cleaning", "eventdetection",
                         "peakfinding", "peakcalling")))

_scripting.importjupyter(locals(),
                         *(f"{i}.__scripting__.holoviewing" for i in
                           ("data", "cleaning", "qualitycontrol", "eventdetection",
                            "peakfinding", "peakcalling", "ramp")))

getLogger(__name__).info(f'{version.version()}{" for jupyter" if _scripting.ISJUP else ""}')
del _scripting, getLogger
