#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Interval detection: finding flat sections in the signal"
import numpy as np

from  utils        import initdefaults
from  signalfilter import PrecisionAlg
from .splitting    import SplitDetector, MultiGradeSplitDetector
from .merging      import MultiMerger, EventMerger, EventSelector

class EventDetector(PrecisionAlg):
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
    split: SplitDetector = MultiGradeSplitDetector()
    merge: EventMerger   = MultiMerger()
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
