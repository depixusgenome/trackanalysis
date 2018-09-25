#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors for storing gui data"
from   typing                     import Dict, Tuple, List, Optional, Sequence
from   copy                       import copy

from   data                       import BEADKEY
from   control.processor.taskview import TaskViewProcessor
from   control.modelaccess        import ReplaceProcessors
from   model.task                 import RootTask
from   peakfinding.selector       import PeakSelectorDetails
from   peakfinding.processor      import PeakSelectorProcessor, PeakSelectorTask, PeaksDict
from   peakcalling.processor      import FitToReferenceTask, FitToReferenceDict, FitBead
from   sequences.modelaccess      import SequencePlotModelAccess

class GuiPeaksDict(PeaksDict):  # pylint: disable=too-many-ancestors
    "gui version of PeaksDict"
    def compute(self, ibead, precision: float = None):
        "Computes values for one bead"
        evts = iter(i for _, i in self.data[ibead,...]) # type: ignore
        prec = self._precision(ibead, precision)
        dtl  = self.config.detailed(evts, prec)

        self.cache.clear()
        self.cache.append(dtl)

        ret            = tuple(self.config.details2output(dtl))
        dtl.histogram *= 100./(max(self.config.histogram.kernelarray())*self.track.ncycles)
        return ret

STORE_T = List[PeakSelectorDetails] # pylint: disable=invalid-name
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

CACHE_T = Dict[BEADKEY, Tuple[float, float]] # pylint: disable=invalid-name
class GuiFitToReferenceDict(FitToReferenceDict): # pylint: disable=too-many-ancestors
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
        fits = None if view is None or self.bead not in view.keys() else view[self.bead]

    return (fits        if self.identification.task is not None else None,
            dtlstore[0] if dtlstore and len(dtlstore[0].peaks)  else None)

def runrefbead(self, ref: RootTask, bead: BEADKEY
              ) -> Tuple[Sequence, Optional[PeakSelectorDetails]]:
    "runs the reference bead with specific processors"
    dtlstore = [] # type: List[PeakSelectorDetails]
    proc     = GuiPeakSelectorProcessor(dtlstore)
    ctrl     = self.tasks.processors(ref, PeakSelectorTask)
    with ReplaceProcessors(ctrl, proc, copy = True) as view:
        pks = view[bead] if view is not None else ()
    return pks, (dtlstore[0] if dtlstore else None)
