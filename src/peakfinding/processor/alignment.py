#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to cycle alignment"
from   typing               import Dict     # pylint: disable=unused-import
from   functools            import partial

import numpy                as     np       # pylint: disable=unused-import

from   model                import Task, Level
from   control.processor    import Processor
from   signalfilter         import rawprecision
from   data.views           import BEADKEY  # pylint: disable=unused-import
from   ..alignment          import PeakCorrelationAlignment

class PeakCorrelationAlignmentTask(PeakCorrelationAlignment, Task):
    "Aligns cycles using peaks"
    level = Level.event
    def __init__(self, **kwa):
        Task.__init__(self)
        super().__init__(**kwa)

class PeakCorrelationAlignmentProcessor(Processor[PeakCorrelationAlignmentTask]):
    "Groups events per peak"
    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    @classmethod
    def _action(cls, tsk, cache, frame, info):
        deltas = cache.get(info[0][0], None)
        if deltas is None:
            precision = rawprecision(frame.data.track, info[0][0])
            data      = tuple(i for _, i in frame.data[info[0][0], ...])
            cache[info[0][0]] = deltas = tsk(data, precision)

        info[1]['data'] += deltas[info[0][1]]
        return info

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        if toframe is None:
            return partial(cls.apply, **cnf)
        cache = dict() # type: Dict[BEADKEY, np.ndarray]
        tsk   = PeakCorrelationAlignment(**cnf)
        return toframe.new().withaction(partial(cls._action, tsk, cache), beadsonly = True)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))
