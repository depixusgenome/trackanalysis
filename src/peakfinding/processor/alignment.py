#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to cycle alignment"
from   typing               import Dict
from   functools            import partial

import numpy                as     np

from   signalfilter          import rawprecision
from   taskmodel             import Task, Level
from   taskcontrol.processor import Processor
from   ..alignment           import (PeakCorrelationAlignment, MinBiasPeakAlignment,
                                     GELSPeakAlignment)

class PeakCorrelationAlignmentTask(PeakCorrelationAlignment, Task):
    """
    Aligns cycles by minimizing the peak widths in a histogram of all peaks.
    """
    if __doc__:
        __doc__ += getattr(PeakCorrelationAlignment, '__doc__')
    level   = Level.event
    def __init__(self, **kwa):
        Task.__init__(self)
        super().__init__(**kwa)

class PeakCorrelationAlignmentProcessor(Processor[PeakCorrelationAlignmentTask]):
    """
    Aligns cycles by minimizing the peak widths in a histogram of all peaks.
    """
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
        if toframe is None:
            return partial(cls.apply, **cnf)
        cache: Dict[int, np.ndarray] = dict()
        tsk                          = PeakCorrelationAlignment(**cnf)
        return toframe.new().withaction(partial(cls._action, tsk, cache))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

class MinBiasPeakAlignmentTask(MinBiasPeakAlignment, Task):
    """
    Aligns cycles.
    """
    if __doc__:
        __doc__ += MinBiasPeakAlignment.__doc__
    level = Level.peak
    def __init__(self, **kwa):
        MinBiasPeakAlignment.__init__(self, **kwa)
        Task.__init__(self, **kwa)

class MinBiasPeakAlignmentProcessor(Processor[MinBiasPeakAlignmentTask]):
    "Aligns cycles."
    if __doc__:
        __doc__ = MinBiasPeakAlignmentTask.__doc__

    @staticmethod
    def _action(tsk, _, info):
        return info[0], tsk.correctevents(info[1])

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        if toframe is None:
            return partial(cls.apply, **cnf)
        return toframe.new().withaction(partial(cls._action,  cls.newtask(**cnf)))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

class GELSPeakAlignmentTask(GELSPeakAlignment, Task):
    """
    Aligns cycles.
    """
    if __doc__:
        __doc__ += MinBiasPeakAlignment.__doc__
    level = Level.peak
    def __init__(self, **kwa):
        GELSPeakAlignment.__init__(self, **kwa)
        Task.__init__(self, **kwa)

class GELSPeakAlignmentProcessor(Processor[GELSPeakAlignmentTask]):
    "Aligns cycles"
    if __doc__:
        __doc__ = GELSPeakAlignmentTask.__doc__

    @staticmethod
    def _action(tsk, _, info):
        return info[0], tsk.correctevents(info[1])

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        if toframe is None:
            return partial(cls.apply, **cnf)
        return toframe.new().withaction(partial(cls._action,  cls.newtask(**cnf)))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))
