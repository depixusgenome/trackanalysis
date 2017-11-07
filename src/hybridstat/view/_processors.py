#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors for storing gui data"
from functools             import partial
from copy                  import copy
from data                  import BEADKEY
from peakfinding.processor import PeakSelectorProcessor, PeaksDict
from peakcalling.processor import FitToReferenceProcessor, FitToReferenceDict

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

class GuiPeakSelectorProcessor(PeakSelectorProcessor, canregister = False):
    "gui version of PeakSelectorProcessor"
    store = None
    def __call__(self, *args, **kwa):
        cur       = type(self)(*args, **kwa)
        cur.store = self.store
        return cur

    def apply(self, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        cnf = self.keywords(cnf)
        if toframe is None:
            return partial(self.apply, **cnf)
        return toframe.new(GuiPeaksDict, config = cnf, store = self.store)

class GuiFitToReferenceDict(FitToReferenceDict):
    "gui version of FitToReferenceDict"
    def __init__(self, *_, model = None, **kwa):
        super().__init__(**kwa)
        self.model              = model
        self.config             = copy(self.config)
        self.config.defaultdata = True

    def optimize(self, key: BEADKEY, data):
        "computes results for one key"
        assert key is self.model.bead
        params = self.model.fittoreference.params
        if params is None:
            res = super().optimize(key, data)
            self.model.fittoreference.params = res
            return res
        return params

class GuiFitToReferenceProcessor(FitToReferenceProcessor, canregister = False):
    "gui fit to reference"
    model = None
    def __call__(self, *args, **kwa):
        cur       = type(self)(*args, **kwa)
        cur.model = self.model
        return cur

    def apply(self, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        cnf = self.keywords(cnf)
        if toframe is None:
            return partial(self.apply, **cnf)
        return toframe.new(GuiFitToReferenceDict, config = cnf, model = self.model)
