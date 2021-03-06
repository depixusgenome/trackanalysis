#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Default patches for tasks and configs
"""
from itertools    import product
from anastore     import Patches, modifyclasses, RESET, DELETE, TPE
from anastore.api import PATCHES, modifykeys, CNT

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

def _v7(data:dict) -> dict:
    modifyclasses(data, 'peakfinding.processor.singlestrand.SingleStrandTask',
                  dict(__name__ = 'peakfinding.processor.peakfiltering.SingleStrandTask'))
    return data

def _v8(data:dict) -> dict:
    modifyclasses(
        data,
        r'.*model.task.*',
        dict(__name__ = lambda x: x.replace('model.task',  'taskmodel')),
        r'.*model.level.*',
        dict(__name__ = lambda x: x.replace('model.', 'taskmodel.')),
        r'.*model.__scripting__.*',
        dict(__name__ = lambda x: x.replace('model.', 'taskmodel.'))
    )
    return data

def _v9(data:dict) -> dict:
    modifyclasses(
        data, ".*cleaning.datacleaning.*",
        dict(__name__ = lambda x: x.replace("cleaning.datacleaning", "cleaning._core"))
    )
    return data

def _v10(data:dict) -> dict:
    modifyclasses(data, "data.Track", dict(_rawprecisions = DELETE, rawprecisions = DELETE))
    return data

def _v11(data:dict) -> dict:
    modifyclasses(
        data, "peakcalling.view._model.*",
        dict(__name__ = lambda x: x.replace('view._model', 'model'))
    )
    return data


__TASKS__        = Patches(_v0task, _v1, _v2, _v3, _v4tasks, _v5, _v6, _v7, _v8, _v9, _v10, _v11)
PATCHES['tasks'] = __TASKS__

def _v0cnf(data:dict) -> dict:
    data = _v0task(data)
    data.get('config', {}).pop('precision.max', None)
    return data

def _v9cnf(data:dict) -> dict:
    modifykeys(data, "theme.cyclehist.plot.cycle",  "figsize",  CNT, lambda _: [600, 597, 'fixed'])
    modifykeys(data, "theme.cyclehist.plot.hist",   "figsize",  CNT, lambda _: [600, 597, 'fixed'])
    return data


__CONFIGS__       = Patches(_v0cnf, _v1, _v2, _v3, _v5, _v6, _v7, _v8, _v9cnf, _v9, _v10, _v11)
PATCHES['config'] = __CONFIGS__
