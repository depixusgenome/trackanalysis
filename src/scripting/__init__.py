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
from   utils.scripting              import *
from   eventdetection.processor     import ExtremumAlignmentTask, EventDetectionTask
from   peakfinding.processor        import PeakSelectorTask
import sequences
import anastore

def _run(locs):
    from utils.scripting import run as scr
    mods = "model", "app", "data", "cleaning", "eventdetection", "peakfinding", "peakcalling"
    hvs  = ("data", "cleaning", "eventdetection", "peakfinding", "peakcalling",
            "qualitycontrol", "ramp")
    scr(locals(),
        scripting   = (("signalfilter", "utils.datadump")
                       + tuple(f"{i}.__scripting__" for i in mods)),
        holoviewing = (f"{i}.__scripting__.holoviewing" for i in hvs))

    locs.pop('_run', None)
_run(locals())
