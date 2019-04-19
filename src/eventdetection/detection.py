#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: finding flat sections in the signal"
import numpy as np

from  utils        import initdefaults
from  signalfilter import PrecisionAlg, CppPrecisionAlg
from .splitting    import SplitDetector, PyMultiGradeSplitDetector
from .merging      import PyMultiMerger, EventMerger, PyEventSelector
from ._core        import EventDetector as _EventDetector # pylint: disable=import-error

class PyEventDetector(PrecisionAlg):
    """
    Detect, merge and select flat intervals in `PHASE.measure`

    # Attributes

    * `split`: splits the data into too many intervals. This is based on a grade
    computed for each frame indicating the likelihood that an event is finished.
    See `eventdetection.splitting` for the available grades.

    * `merge`: merges the previous intervals when the difference between their
    population is not statistically relevant.

    * `select`: possibly clips events and discards those too small.
    """
    split: SplitDetector = PyMultiGradeSplitDetector()
    merge: EventMerger   = PyMultiMerger()
    select               = PyEventSelector()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def compute(self, data:np.ndarray, precision: float) -> np.ndarray:
        "computes the intervals"
        return self.select(data, self.merge(data, self.split(data, precision), precision))

    def __call__(self, data:np.ndarray, precision: float = None)-> np.ndarray:
        precision = self.getprecision(precision, data)
        return self.select(data, self.merge(data, self.split(data, precision), precision))

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)

class EventDetector(CppPrecisionAlg, _EventDetector, zattributes = ('precision', 'merge')):
    """
    Detect, merge and select flat intervals in `PHASE.measure`

    # Attributes

    * `split`: splits the data into too many intervals. This is based on a grade
    computed for each frame indicating the likelihood that an event is finished.
    See `eventdetection.splitting` for the available grades.

    * `merge`: merges the previous intervals when the difference between their
    population is not statistically relevant.

    * `select`: possibly clips events and discards those too small.
    """
    split: SplitDetector
    merge: EventMerger
    def __init__(self, **kwa):
        CppPrecisionAlg.__init__(self, **kwa)
        _EventDetector.__init__(self, **kwa)

    def __call__(self, data:np.ndarray, precision: float = None):
        return self.compute(data, self.getprecision(precision, data))

    @classmethod
    def run(cls, *args, **kwa):
        "instantiates and calls class"
        return cls(**kwa)(*args)
