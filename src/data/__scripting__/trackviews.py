#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkeypatches as follows
    * Beads, Cycles:

        * can filter their output using *withfilter*

    * Beads, Cycles, Events:

        * *withcopy(True)* is called in the *__init__* by default
        * a *rawprecision* method is added
        * *with...* methods return an updated copy
"""
from typing                 import List
from functools              import partial
from signalfilter           import NonLinearFilter
from taskcontrol.processor  import ProcessorException
from ..views                import Beads, Cycles

def _action(filt, frame, info):
    return (info[0], filt(info[1], precision = frame.track.rawprecision(info[0])))

def _withfilter(self, tpe = NonLinearFilter, **kwa):
    "applies the filter to the data"
    return self.withaction(partial(_action, tpe(**kwa)))

def _isok(self, key) -> bool:
    """Returns True if the bead has *not* been removed by a cleaning Task,
    or no cleaning has been run yet."""
    try:
        self[key]
    except ProcessorException:
        return False
    return True

for _cls in (Beads, Cycles):
    _cls.withfilter = _withfilter
    _cls.isok = _isok


__all__: List[str] = []
