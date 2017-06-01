#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tasks related to peakfinding"
from typing             import (Iterator, Tuple, # pylint: disable=unused-import
                                Sequence, List, Set, Optional)

from model.task         import Task, Level
from control.processor  import Processor
from data.trackitems    import BEADKEY, TrackItems, Beads
from signalfilter       import rawprecision
from .alignment         import PeakCorrelationAlignment
from .selector          import PeakSelector, Output as PeakOutput

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
        yield from self.config(vals, self.__precision(ibead, precision))

    def detailed(self, ibead, precision: float = None):
        "detailed output from config"
        return self.config.detailed(iter(i for _, i in self.data[ibead,...]),
                                    self.__precision(ibead, precision))

    def _keys(self, sel:Sequence = None, _ = None) -> Iterator[BEADKEY]:
        if self.__keys is None:
            self.__keys = frozenset(i for i, _ in self.data.keys() if Beads.isbead(i))

        if sel is None:
            yield from self.__keys
        else:
            yield from (i for i in self.__keys if i in sel)

    def _iter(self, sel:Sequence = None) -> Iterator[Output]:
        yield from ((bead, self.compute(bead)) for bead in self.keys(sel))

    def __precision(self, ibead: int, precision: Optional[float]):
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
