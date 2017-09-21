#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to peakfinding"
from typing                 import Dict     # pylint: disable=unused-import
from functools              import partial

import numpy                as     np       # pylint: disable=unused-import

from utils                  import initdefaults
from model                  import Task, Level, PHASE
from control.processor      import Processor
from signalfilter           import rawprecision
from data.views             import BEADKEY  # pylint: disable=unused-import
from eventdetection.data    import EventDetectionConfig
from .alignment             import PeakCorrelationAlignment
from .selector              import PeakSelector
from .probabilities         import Probability

# pylint: disable=unused-import
from .data                  import PeaksDict, Output
from .dataframe             import PeaksDataFrameFactory

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
    def __action(cls, cnf):
        cache = dict() # type: Dict[BEADKEY, np.ndarray]
        tsk   = PeakCorrelationAlignment(**cnf)
        def _action(frame, info):
            nonlocal cache
            deltas = cache.get(info[0][0], None)
            if deltas is None:
                precision = rawprecision(frame.data.track, info[0][0])
                data      = tuple(i for _, i in frame[info[0][0], ...])
                cache[info[0][0]] = deltas = tsk(data, precision)

            info[1]['data'] += deltas[info[0][1]]
            return info
        return _action

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        fcn = lambda frame: (frame
                             .new()
                             .withaction(cls.__action(cnf), beadsonly = True))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

class PeakSelectorTask(PeakSelector, Task):
    "Groups events per peak"
    levelin = Level.event
    levelou = Level.peak
    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    def __init__(self, **kwa):
        Task.__init__(self)
        PeakSelector.__init__(self, **kwa)

class PeakSelectorProcessor(Processor[PeakSelectorTask]):
    "Groups events per peak"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        fcn = lambda frame: frame.new(PeaksDict, config = cnf)
        return fcn if toframe is None else fcn(toframe)
    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()), levels = self.levels)

class PeakProbabilityTask(Task):
    "Computes probabilities for each peak"
    level              = Level.peak
    minduration: float = None
    framerate:   float = None
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class PeakProbabilityProcessor(Processor[PeakProbabilityTask]):
    "Computes probabilities for each peak"
    @staticmethod
    def __action(minduration, framerate, frame, info):
        rate = frame.track.framerate if framerate is None else framerate
        prob = Probability(minduration = minduration, framerate = rate)
        ends = frame.track.phaseduration(..., PHASE.measure)
        return info[0], iter((i[0], prob(i[1], ends)) for i in info[1])

    @classmethod
    def apply(cls, toframe = None, model = None, minduration = None, framerate = None, **_):
        "applies the task to a frame or returns a function that does so"
        if minduration is None:
            events      = next(i for i in tuple(model)[::-1]
                               if isinstance(i, EventDetectionConfig))
            minduration = events.events.select.minduration

        fcn = lambda i: i.withaction(partial(cls.__action, minduration, framerate))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(model = args.model, **self.config()))
