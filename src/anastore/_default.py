#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
patches for tasks and configs
"""
from ._patches  import Patches, modifyclasses

def _v0(data:dict) -> dict:
    modifyclasses(data,
                  "eventdetection.processor.ExtremumAlignmentTask",
                  dict(edge = lambda val: 'right' if val else None))

    data.get('config', {}).pop('precision.max', None)
    return data

__TASKS__   = Patches(_v0)
__CONFIGS__ = Patches(_v0)
