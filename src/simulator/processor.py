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
        cpy = self.task.config()
        def _gen():
            yield TrackSimulator(**cpy).track(cpy['nbeads'], cpy['seed']).beads

        args.apply(_gen(), levels = self.levels)
