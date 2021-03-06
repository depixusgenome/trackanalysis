#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors for storing gui data"
from   typing                         import Tuple, List, Optional, Sequence
from   copy                           import copy

from   cleaning.processor             import DataCleaningException
from   peakfinding.selector           import PeakSelectorDetails
from   peakfinding.processor          import (PeakSelectorProcessor, PeakSelectorTask,
                                              PeaksDict, SingleStrandProcessor)
from   peakcalling.processor          import (FitToReferenceTask, FitToReferenceDict,
                                              FitToHairpinTask)
from   taskcontrol.processor.taskview import TaskViewProcessor
from   taskcontrol.modelaccess        import ReplaceProcessors
from   taskmodel                      import RootTask, Level

class GuiPeakSelectorDetails(PeakSelectorDetails):
    "gui version of PeakSelectorDetails"
    __slots__ = ['maxlength']
    def __init__(self, *args, **kwa):
        super().__init__(*args, **kwa)
        self.maxlength = None

    def output(self, zmeasure):
        "yields results from precomputed details"
        out = super().output(zmeasure)
        return out[:self.maxlength] if self.maxlength else out

class GuiPeaksDict(PeaksDict):  # pylint: disable=too-many-ancestors
    "gui version of PeaksDict"
    def compute(self, ibead, precision: float = None):
        "Computes values for one bead"
        evts = iter(i for _, i in self.data[ibead,...]) # type: ignore
        prec = self._precision(ibead, precision)
        dtl  = self.config.detailed(evts, prec)

        dtl.histogram *= 100./(max(self.config.histogram.kernelarray())*self.track.ncycles)

        self.cache.clear()
        self.cache.append(GuiPeakSelectorDetails(dtl.positions,     dtl.histogram,
                                                 dtl.minvalue,      dtl.binwidth,
                                                 dtl.corrections,   dtl.peaks,
                                                 dtl.events,        dtl.ids))

        return tuple(self.config.details2output(dtl))

class GuiPeakSelectorProcessor(PeakSelectorProcessor):
    "gui version of PeakSelectorProcessor"
    def __init__(self, store, **kwa):
        super().__init__(**kwa)
        self.store = store

    def __call__(self, **_):
        self.__init__(self.store, **_)
        return self

    def createcache(self, _):
        "creates the cache"
        return self.store

    taskdicttype = classmethod(lambda cls: GuiPeaksDict) # type: ignore

class GuiSingleStrandProcessor(SingleStrandProcessor):
    "gui version of PeakSelectorProcessor"
    def __init__(self, store = None, **kwa):
        super().__init__(**kwa)
        self.store: List[PeakSelectorDetails] = [] if store is None else store

    def __call__(self, **_):
        self.__init__(self.store, **_)
        return self

    def remove(self, frame, info):
        info                    = super().remove(frame, info)
        self.store[0].maxlength = len(info[1])
        return info

    def config(self):
        "returns the config"
        cnf = super().config()
        cnf['store'] = self.store
        return cnf

class GuiFitToReferenceDict(FitToReferenceDict): # pylint: disable=too-many-ancestors
    "gui version of FitToReferenceDict"
    def __init__(self, *args, **kwa):
        super().__init__(*args, **kwa)
        self.config             = copy(self.config)
        self.config.defaultdata = True

    def optimize(self, key: int, data):
        "computes results for one key"
        params = self.cache[0].get(key, None)
        if params is None:
            self.cache[0][key] = params = super().optimize(key, data)

        if self.cache[1] and self.cache[1][0] and params != (1., 0.):
            self.cache[1][0].transform(params)
        return params

class GuiFitToReferenceProcessor(TaskViewProcessor[FitToReferenceTask,
                                                   GuiFitToReferenceDict,
                                                   int]):
    "Changes the Z axis to fit the reference"
    def __init__(self, store, **kwa):
        super().__init__(**kwa)
        self.store = store

    def __call__(self, **_):
        self.__init__(self.store, **_)
        return self

    def createcache(self, _):
        "creates the cache"
        return self.store

def runbead(ctrl, bead, refcache):
    "runs the bead with specific processors"
    if ctrl is None:
        return None

    cache = ctrl.data.setcachedefault(-1, {})
    out   = cache.get(bead, None)
    if out is None:
        store: List[PeakSelectorDetails] = []

        procs = (GuiPeakSelectorProcessor(store),
                 GuiFitToReferenceProcessor((refcache, store)),
                 GuiSingleStrandProcessor(store))
        ident = any(isinstance(i, FitToHairpinTask) for i in ctrl.model)
        with ReplaceProcessors(ctrl, *procs, copy = True) as view:
            if view is None or view.level.value < Level.peak.value or bead not in view.keys():
                out = None, None
            else:
                try:
                    tmp = view[bead]
                except DataCleaningException as exc:
                    out = cache[bead] = exc
                else:
                    out = (tmp      if ident                         else None,
                           store[0] if store and len(store[0].peaks) else None)
                    cache[bead] = out
    return out

def runrefbead(self, ref: RootTask, bead: int
              ) -> Tuple[Sequence, Optional[PeakSelectorDetails]]:
    "runs the reference bead with specific processors"
    dtlstore: List[PeakSelectorDetails] = []
    procs    = (GuiPeakSelectorProcessor(dtlstore),
                GuiSingleStrandProcessor(dtlstore))
    ctrl     = self.tasks.processors(ref, PeakSelectorTask)
    with ReplaceProcessors(ctrl, *procs, copy = True) as view:
        pks = view[bead] if view is not None else ()
    return pks, (dtlstore[0] if dtlstore else None)
