#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: finding flat sections in the signal"
import numpy as np

from  utils        import initdefaults
from  signalfilter import PrecisionAlg
from .splitting    import SplitDetector, DerivateSplitDetector
from .merging      import KnownSigmaEventMerger, EventMerger, EventSelector

class EventDetector(PrecisionAlg):
    "detects, mergers and selects intervals"
    split: SplitDetector = DerivateSplitDetector()
    merge: EventMerger   = KnownSigmaEventMerger()
    select               = EventSelector()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __call__(self, data:np.ndarray, precision: float = None):
        precision = self.getprecision(precision, data)
        return self.select(data, self.merge(data, self.split(data, precision), precision))

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)
