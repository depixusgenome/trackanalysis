#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors for storing gui data"
from   typing                     import Dict, Tuple, List, Optional
from   copy                       import copy
import numpy                      as     np

from   data                       import BEADKEY
from   control.processor.taskview import TaskViewProcessor
from   control.modelaccess        import ReplaceProcessors
from   model.task                 import RootTask
from   peakfinding.selector       import PeakSelectorDetails
from   peakfinding.processor      import PeakSelectorProcessor, PeakSelectorTask, PeaksDict
from   peakcalling.processor      import FitToReferenceTask, FitToReferenceDict, FitBead
from   sequences.modelaccess      import SequencePlotModelAccess

class GuiPeaksDict(PeaksDict):
    "gui version of PeaksDict"
    def compute(self, ibead, precision: float = None):
        "Computes values for one bead"
        evts = iter(i for _, i in self.data[ibead,...]) # type: ignore
        prec = self._precision(ibead, precision)
        dtl  = self.config.detailed(evts, prec)

        self.cache.clear()
        self.cache.append(dtl)
        return tuple(self.config.details2output(dtl))

STORE_T = List[PeakSelectorDetails]
class GuiPeakSelectorProcessor(PeakSelectorProcessor):
    "gui version of PeakSelectorProcessor"
    def __init__(self, store, **kwa):
        super().__init__(**kwa)
        self.store              = store

    def __call__(self, **_):
        self.__init__(self.store, **_)
        return self

    def createcache(self, _):
        "creates the cache"
        return self.store

    taskdicttype = classmethod(lambda cls: GuiPeaksDict) # type: ignore

CACHE_T = Dict[BEADKEY, Tuple[float, float]]
class GuiFitToReferenceDict(FitToReferenceDict):
    "gui version of FitToReferenceDict"
    def __init__(self, *args, **kwa):
        super().__init__(*args, **kwa)
        self.config             = copy(self.config)
        self.config.defaultdata = True

    def optimize(self, key: BEADKEY, data):
        "computes results for one key"
        params = self.cache[0].get(key, None)
        if params is None:
            self.cache[0][key] = params = super().optimize(key, data)

        if self.cache[1] and self.cache[1][0] and params != (1., 0.):
            self.cache[1][0].transform(params)
        return params

class GuiFitToReferenceProcessor(TaskViewProcessor[FitToReferenceTask,
                                                   GuiFitToReferenceDict,
                                                   BEADKEY]):
    "Changes the Z axis to fit the reference"
    def __init__(self, store, **kwa):
        super().__init__(**kwa)
        self.store = store

    def __call__(self, **_):
        self.__init__(self.store, **_)
        return self

    def createcache(self, args):
        "creates the cache"
        cache = args.data.setCacheDefault(self, {})
        return cache, self.store

def runbead(self) -> Tuple[Optional[FitBead], Optional[PeakSelectorDetails]]:
    "runs the bead with specific processors"
    dtlstore = [] # type: List[PeakSelectorDetails]
    procs    = GuiPeakSelectorProcessor(dtlstore), GuiFitToReferenceProcessor(dtlstore)
    ctx      = SequencePlotModelAccess.runcontext(self, *procs)
    with ctx as view:
        fits = None if view is None else view[self.bead]
    return (fits        if self.identification.task is not None else None,
            dtlstore[0] if dtlstore and len(dtlstore[0].peaks)  else None)

def runrefbead(self, ref: RootTask, bead: BEADKEY
              ) -> Tuple[Optional[np.ndarray], Optional[PeakSelectorDetails]]:
    "runs the reference bead with specific processors"
    dtlstore = [] # type: List[PeakSelectorDetails]
    proc     = GuiPeakSelectorProcessor(dtlstore)
    with ReplaceProcessors(self.processors(ref, PeakSelectorTask), proc) as view:
        try:
            pks = np.array([i for i, _ in view[bead]], dtype = 'f4')
        except: # pylint: disable=bare-except
            pks = np.empty((0,), dtype = 'f4')

    if dtlstore:
        rho = max(self.task(ref, PeakSelectorTask).histogram.kernelarray())
        dtlstore[0].histogram *= 100./(self.track(ref).ncycles*rho)
    return pks, (dtlstore[0] if dtlstore else None)
