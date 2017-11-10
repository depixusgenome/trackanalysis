#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors for storing gui data"
from functools                  import partial
from data                       import BEADKEY
from control.processor.taskview import TaskViewProcessor
from peakfinding.processor      import PeakSelectorProcessor, PeaksDict
from peakcalling.processor      import FitToReferenceTask, FitToReferenceDict

class GuiPeaksDict(PeaksDict):
    "gui version of PeaksDict"
    def __init__(self, *_, store = None, **kwa):
        super().__init__(**kwa)
        self.store = store

    def compute(self, ibead, precision: float = None):
        "Computes values for one bead"
        evts = iter(i for _, i in self.data[ibead,...]) # type: ignore
        prec = self._precision(ibead, precision)
        dtl  = self.detailed(evts, prec)

        self.store[0] = dtl
        yield from self.details2output(dtl)

class GuiPeakSelectorProcessor(PeakSelectorProcessor):
    "gui version of PeakSelectorProcessor"
    def __init__(self, store: list = None, **kwa) -> None:
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

class CachedFitToReferenceDict(FitToReferenceDict):
    "gui version of FitToReferenceDict"
    def __init__(self, *_, cache = None, **kwa):
        super().__init__(**kwa)
        self.cache = cache

    def optimize(self, key: BEADKEY, data):
        "computes results for one key"
        if self.cache is None:
            return super().optimize(key, data)

        params = self.cache.get(key, None)
        if params is None:
            self.cache[key] = params = super().optimize(key, data)
        return params

class GuiFitToReferenceProcessor(TaskViewProcessor[FitToReferenceTask,
                                                   CachedFitToReferenceDict,
                                                   BEADKEY]):
    "Changes the Z axis to fit the reference"
    def run(self, args):
        "updates the frames"
        cache = args.data.setCacheDefault(self, dict())
        args.apply(self.apply(cache = cache, **self.config()))
