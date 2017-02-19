#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from typing     import Optional # pylint: disable=unused-import

from model.task import ItemFunctorTask, Level
from .selector  import PeakSelector

class PeakSelectorTask(PeakSelector, ItemFunctorTask):
    u"Groups events per peak"
    levelin = Level.event
    levelou = Level.peak
    def __init__(self, **kwa):
        ItemFunctorTask.__init__(self)
        PeakSelector.__init__(self, **kwa)

    @staticmethod
    def __functor__(cnf, data):
        def _run(ibead):
            vals = iter(i for _, i in data[ibead,:])
            return cnf(vals, cnf.rawprecision(data.track, ibead))

        for bead in frozenset(i[0] for i in data.keys()):
            yield (bead, _run(bead))
