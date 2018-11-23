#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default patches for tasks and configs
"""
from  itertools import product
from ._patches  import Patches, modifyclasses, RESET, DELETE, TPE

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

def _v3(data:dict) -> dict:
    repl = lambda x: x.replace('Min', '')
    modifyclasses(data,
                  "peakfinding.selector.PeakSelector", dict(align = DELETE),
                  r"cleaning.datacleaning.Min(\w+)",   dict(__name__ = repl))
    return data

def _v4tasks(data:dict) -> dict:
    if isinstance(data, list):
        data = {'tasks': [data]}
    cnf = data.get("config", ())
    for  i, j in (("probes", "tasks.oligos"), ("path", "tasks.sequence.path")):
        if j in cnf:
            data.setdefault("sequence", {})[i] = cnf[j]
    return data

def _v5(data:dict) -> dict:
    mdl  = 'eventdetection.merging.'
    args = zip(('HeteroscedasticEventMerger', 'PopulationMerger', 'RangeMerger'),
               ('stats', 'pop', 'range'))
    def _multi(itm):
        itm.update({k: i for i, (j, k) in product(itm.pop('merges', ()), args)
                    if i[TPE] == mdl+j})

    modifyclasses(data, mdl+"MultiMerger", dict(__call__ = _multi))
    return data

def _v6(data:dict) -> dict:
    modifyclasses(data, 'cleaning.beadsubtraction.BeadSubtractionTask',
                  dict(__name__ = 'cleaning.processor.BeadSubtractionTask'))
    return data

__TASKS__   = Patches(_v0task, _v1, _v2, _v3, _v4tasks, _v5, _v6)

def _v0cnf(data:dict) -> dict:
    data = _v0task(data)
    data.get('config', {}).pop('precision.max', None)
    return data
__CONFIGS__ = Patches(_v0cnf, _v1, _v2, _v3, _v5, _v6)
