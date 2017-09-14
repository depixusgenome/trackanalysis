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
from ..views                import Beads, Cycles

def _action(filt, frame, info):
    return (info[0], filt(info[1], precision = frame.track.rawprecision(info[0])))

def _withfilter(self, tpe = NonLinearFilter, **kwa):
    "applies the filter to the data"
    return self.withaction(partial(_action, tpe(**kwa)))

for _cls in (Beads, Cycles):
    _cls.withfilter = _withfilter

__all__: List[str] = []
