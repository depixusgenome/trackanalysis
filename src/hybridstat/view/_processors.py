#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors for storing gui data"
from typing                     import Dict, Tuple, List, Optional
from functools                  import partial
from data                       import BEADKEY
from control.processor.taskview import TaskViewProcessor
from peakfinding.selector       import PeakSelectorDetails
from peakfinding.processor      import PeakSelectorProcessor, PeaksDict
from peakcalling.processor      import FitToReferenceTask, FitToReferenceDict, FitBead
from sequences.modelaccess      import SequencePlotModelAccess

class GuiPeaksDict(PeaksDict):
    "gui version of PeaksDict"
    def __init__(self, *_, store = None, **kwa):
        super().__init__(**kwa)
        self.store = store

    def compute(self, ibead, precision: float = None):
        "Computes values for one bead"
        evts = iter(i for _, i in self.data[ibead,...]) # type: ignore
        prec = self._precision(ibead, precision)
        dtl  = self.config.detailed(evts, prec)

        self.store.clear()
        self.store.append(dtl)
        yield from self.config.details2output(dtl)

STORE_T = List[PeakSelectorDetails]
class GuiPeakSelectorProcessor(PeakSelectorProcessor):
    "gui version of PeakSelectorProcessor"
    def __init__(self, store: STORE_T = None, **kwa) -> None:
        super().__init__(**kwa)
        self.store = store

    def __call__(self, *args, **kwa):
        return type(self)(self.store, *args, **kwa)

    def apply(self, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        cnf = self.keywords(cnf)
        if toframe is None:
            return partial(self.apply, **cnf)
        return toframe.new(GuiPeaksDict, config = cnf, store = self.store)

CACHE_T = Dict[BEADKEY, Tuple[float, float]]
class GuiFitToReferenceDict(FitToReferenceDict):
    "gui version of FitToReferenceDict"
    def __init__(self, *_, cache = None, **kwa):
        super().__init__(**kwa)
        self.cache: CACHE_T = cache[0] if cache else {}
        self.store: STORE_T = cache[1] if cache else []

    def optimize(self, key: BEADKEY, data):
        "computes results for one key"
        params = self.cache.get(key, None)
        if params is None:
            self.cache[key] = params = super().optimize(key, data)

        if self.store and self.store[0]:
            self.store[0].transform(params)
        return params

class GuiFitToReferenceProcessor(TaskViewProcessor[FitToReferenceTask,
                                                   GuiFitToReferenceDict,
                                                   BEADKEY]):
    "Changes the Z axis to fit the reference"
    def __init__(self, store: STORE_T = None, **kwa) -> None:
        super().__init__(**kwa)
        self.store = store

    def __call__(self, *args, **kwa):
        return type(self)(self.store, *args, **kwa)

    def run(self, args):
        "updates the frames"
        cache = args.data.setCacheDefault(self, dict())
        args.apply(self.apply(cache = (cache, self.dtlstore), **self.config()))

def runbead(self) -> Tuple[Optional[FitBead], Optional[PeakSelectorDetails]]:
    "runs the bead with specific processors"
    dtlstore = [] # type: List[PeakSelectorDetails]
    procs    = (GuiPeakSelectorProcessor(dtlstore),
                GuiFitToReferenceProcessor(dtlstore))
    view     = SequencePlotModelAccess.runbead(self, *procs)
    if view is None:
        return None, None

    fits = view[self.bead]

    if not dtlstore or len(dtlstore[0].peaks) == 0:
        return None, None
    if not self.identification.task:
        return None, dtlstore[0]
    return fits, dtlstore[0]
