#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from typing             import Iterator, Tuple
from functools          import partial

from model.task         import Task, Level
from control.processor  import Processor
from data.trackitems    import BEADKEY
from .selector          import PeakSelector, Output as PeakOutput

class PeakSelectorTask(PeakSelector, Task):
    u"Groups events per peak"
    levelin = Level.event
    levelou = Level.peak
    def __init__(self, **kwa):
        Task.__init__(self)
        PeakSelector.__init__(self, **kwa)

Output = Tuple[BEADKEY, Iterator[PeakOutput]]
class PeakSelectorProcessor(Processor):
    u"Groups events per peak"
    @staticmethod
    def apply(cnf, data) -> Iterator[Output]:
        u"runs over one frame"
        def _run(ibead):
            vals = iter(i for _, i in data[ibead,...])
            prec = cnf.histogram.rawprecision(data.track, ibead)
            yield from cnf(vals, prec)

        return ((bead, _run(bead)) for bead in frozenset(i[0] for i in data.keys()))

    def run(self, args):
        args.apply(partial(self.apply, self.caller()), levels = self.levels)
