#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Patches for tasks and configs.

Please check the *modifyclasses* documentation.


**Note**: If a default value has changed, do not set to the new value.  Return
or raise *RESET*.

**Note**: If a value should be set to default, do not set it.  Return or raise
*RESET*.
"""
from ._patches  import Patches, modifyclasses, RESET

def _v0task(data:dict) -> dict:
    modifyclasses(data,
                  "eventdetection.processor.ExtremumAlignmentTask",
                  dict(edge  = lambda val: 'right' if val else RESET,
                       phase = RESET, factor = RESET))
    return data

__TASKS__   = Patches(_v0task)

def _v0cnf(data:dict) -> dict:
    data = _v0task(data)
    data.get('config', {}).pop('precision.max', None)
    return data
__CONFIGS__ = Patches(_v0cnf)
