#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to peakfinding"
from typing             import (Iterator, Tuple, # pylint: disable=unused-import
                                Sequence, List, Set, Optional)
from functools          import partial
import numpy as np

from utils              import initdefaults
from model              import Task, Level, PHASE
from control.processor  import Processor
from data.trackitems    import BEADKEY, TrackItems, Beads
from signalfilter       import rawprecision
from eventdetection     import EventDetectionConfig
from .alignment         import PeakCorrelationAlignment
from .selector          import PeakSelector, Output as PeakOutput, PeaksArray
from .probabilities     import Probability

class PeakCorrelationAlignmentTask(PeakCorrelationAlignment, Task):
    "Aligns cycles using peaks"
    level = Level.event
    def __init__(self, **kwa):
        Task.__init__(self)
        super().__init__(**kwa)

class PeakCorrelationAlignmentProcessor(Processor):
    "Groups events per peak"
    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    @classmethod
    def __action(cls, frame, cnf):
        cache = dict()
        tsk   = PeakCorrelationAlignment(**cnf)
        def _action(info):
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
                             .withaction(cls.__action(frame, cnf), beadsonly = True))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
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

Output = Tuple[BEADKEY, Iterator[PeakOutput]]
class PeaksDict(TrackItems):
    "iterator over peaks grouped by beads"
    level = Level.peak
    def __init__(self, *_, config = None, **kwa):
        assert len(_) == 0
        super().__init__(**kwa)
        if config is None:
            self.config = PeakSelector()
        elif isinstance(config, dict):
            self.config = PeakSelector(**config)
        else:
            assert isinstance(config, PeakSelector), config
            self.config = config

        self.__keys = None

    def compute(self, ibead, precision: float = None) -> Iterator[PeakOutput]:
        "Computes values for one bead"
        vals = iter(i for _, i in self.data[ibead,...])
        yield from self.config(vals, self._precision(ibead, precision))

    def index(self) -> 'PeaksDict':
        "Returns indexes at the same key and positions"
        return self.withaction(self.__index)

    def withmeasure(self, singles = np.nanmean, multiples = None) -> 'PeaksDict':
        "Returns a measure per events."
        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))
        return self.withaction(partial(self.__measure, singles, multiples))

    @classmethod
    def measure(cls, itm: PeaksArray, singles = np.nanmean, multiples = None) -> PeaksArray:
        "Returns a measure per events."
        if len(itm) == 0:
            return itm

        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))

        if isinstance(itm[0][1], PeaksArray):
            itm[:] = [(i, cls.__array2measure(singles, multiples, j)) for i, j in itm]
        else :
            itm[:] = cls.__array2measure(singles, multiples, itm)
        return itm

    @classmethod
    def __measure(cls, singles, multiples, info):
        return info[0], ((i, cls.__array2measure(singles, multiples, j)) for i, j in info[1])

    @classmethod
    def __index(cls, info):
        return info[0], ((i, cls.__array2range(j)) for i, j in info[1])

    @staticmethod
    def __array2measure(singles, multiples, arr):
        if arr.dtype == 'O':
            arr[:] = [None                  if i is None            else
                      singles  (i[1])       if isinstance(i, tuple) else
                      multiples(i['data'])
                      for i in arr[:]]
        else:
            arr['data'] = [singles(i) for i in arr['data']]
        return arr

    @staticmethod
    def __array2range(arr):
        if arr.dtype == 'O':
            return np.array([None                        if i is None            else
                             range(i[0], i[0]+len(i[1])) if isinstance(i, tuple) else
                             range(i[0][0], i[-1][0]+len(i[-1][1]))
                             for i in arr])
        return np.array([None                        if i is None            else
                         range(i[0], i[0]+len(i[1])) if np.isscalar(i[1][0]) else
                         range(i[0][0], i[-1][0]+len(i[-1][1]))
                         for i in arr])

    def _keys(self, sel:Sequence = None, _ = None) -> Iterator[BEADKEY]:
        if self.__keys is None:
            if isinstance(self.data, PeaksDict):
                self.__keys = frozenset(i for i in self.data.keys() if Beads.isbead(i))
            else:
                self.__keys = frozenset(i for i, _ in self.data.keys() if Beads.isbead(i))

        if sel is None:
            yield from self.__keys
        else:
            yield from (i for i in self.__keys if i in sel)

    def _iter(self, sel:Sequence = None) -> Iterator[Output]:
        yield from ((bead, self.compute(bead)) for bead in self.keys(sel))

    def _precision(self, ibead: int, precision: Optional[float]):
        return self.config.getprecision(precision, self.data.track, ibead)

class PeakSelectorProcessor(Processor):
    "Groups events per peak"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        fcn = lambda frame: frame.new(PeaksDict, config = cnf)
        return fcn if toframe is None else fcn(toframe)
    def run(self, args):
        args.apply(self.apply(**self.config()), levels = self.levels)

class PeakProbabilityTask(Task):
    "Computes probabilities for each peak"
    level       = Level.peak
    minduration = None # type: float
    framerate   = None # type: float
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class PeakProbabilityProcessor(Processor):
    "Computes probabilities for each peak"
    @staticmethod
    def __action(frame, minduration, framerate, info):
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

        fcn = lambda i: i.withaction(partial(cls.__action, i, minduration, framerate))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        args.apply(self.apply(model = args.model, **self.config()))
