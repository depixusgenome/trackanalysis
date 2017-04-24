#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from typing             import (Iterator, Tuple, # pylint: disable=unused-import
                                Optional, Sequence, List, Set)

from model.task         import Task, Level
from control.processor  import Processor
from data.trackitems    import BEADKEY, TrackItems, Beads
from .selector          import PeakSelector, Output as PeakOutput

class PeakSelectorTask(PeakSelector, Task):
    u"Groups events per peak"
    levelin = Level.event
    levelou = Level.peak
    def __init__(self, **kwa):
        Task.__init__(self)
        PeakSelector.__init__(self, **kwa)

Output = Tuple[BEADKEY, Iterator[PeakOutput]]
class PeaksDict(TrackItems):
    u"iterator over peaks grouped by beads"
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

    def _keys(self, sel:Optional[Sequence] = None, _ = None) -> Iterator[BEADKEY]:
        if self.__keys is None:
            self.__keys = frozenset(i for i, _ in self.data.keys() if Beads.isbead(i))

        if sel is None:
            yield from self.__keys
        else:
            yield from (i for i in self.__keys if i in sel)

    def __run(self, ibead) -> Iterator[PeakOutput]:
        vals = iter(i for _, i in self.data[ibead,...])
        prec = self.config.histogram.rawprecision(self.data.track, ibead)
        yield from self.config(vals, prec)

    def _iter(self, sel:Optional[Sequence] = None) -> Iterator[Output]:
        yield from ((bead, self.__run(bead)) for bead in self.keys(sel))

    def detailed(self, ibead, precision = None):
        "detailed output from config"
        if precision is None:
            precision = self.config.histogram.rawprecision(self.data.track, ibead)
        return self.config.detailed(iter(i for _, i in self.data[ibead,...]), precision)

class PeakSelectorProcessor(Processor):
    u"Groups events per peak"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        # pylint: disable=not-callable
        fcn = lambda frame: frame.new(PeaksDict, config = cnf)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        args.apply(self.apply(**self.config()), levels = self.levels)
