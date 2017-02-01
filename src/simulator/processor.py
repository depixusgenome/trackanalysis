#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processes TrackSimulatorTask"

from control.processor  import Processor
from .task              import TrackSimulatorTask
from .track             import TrackSimulator

class TrackSimulatorProcessor(Processor):
    u"Process TrackSimulatorTask"
    tasktype = TrackSimulatorTask
    def run(self, args):
        u"returns a dask delayed item"
        cpy =  TrackSimulator(**self.task.__dict__)
        def _gen(cpy    = cpy,
                 nbeads = self.task.nbeads,
                 seed   = self.task.seed):
            yield cpy.track(nbeads, seed)

        args.apply(_gen(), levels = self.levels)
