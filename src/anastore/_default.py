#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default patches for tasks and configs
"""
from ._patches  import Patches, modifyclasses, RESET

def _v0task(data:dict) -> dict:
    modifyclasses(data,
                  "eventdetection.processor.ExtremumAlignmentTask",
                  dict(edge  = lambda val: 'right' if val else RESET,
                       phase = RESET, factor = RESET))
    return data

def _v1(data:dict) -> dict:
    mods = dict(symmetry = lambda val: 'both' if val else RESET)
    modifyclasses(data,
                  "peakcalling.processor.fittohairpin.FitToHairpinTask", mods,
                  "peakcalling.processor.fittoreference.FitToReferenceTask", mods)
    return data

def _v2(data:dict) -> dict:
    repl = lambda x: (x
                      .replace('.histogram.', '.groupby.histogramfitter.')
                      .replace('.ByZeroCrossing', '.ByHistogram'))
    modifyclasses(data, r"peakfinding.histogram.(\w+)", dict(__name__ = repl))
    return data

__TASKS__   = Patches(_v0task, _v1, _v2)

def _v0cnf(data:dict) -> dict:
    data = _v0task(data)
    data.get('config', {}).pop('precision.max', None)
    return data
__CONFIGS__ = Patches(_v0cnf, _v1, _v2)
