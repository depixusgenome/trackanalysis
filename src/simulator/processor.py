#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processes TrackSimulatorTask"

from control.processor  import Processor
from .task              import TrackSimulatorTask, EventSimulatorTask
from .track             import TrackSimulator
from .peak              import PeakSimulator

class TrackSimulatorProcessor(Processor):
    u"Process TrackSimulatorTask"
    tasktype = TrackSimulatorTask
    def run(self, args):
        u"returns a dask delayed item"
        cpy = self.task.config()
        def _gen():
            yield TrackSimulator(**cpy).track(cpy['nbeads'], cpy['seed']).beads

        args.apply(_gen(), levels = self.levels)

class EventSimulatorProcessor(Processor):
    u"Process TrackSimulatorTask"
    tasktype = EventSimulatorTask
    def run(self, args):
        u"returns a dask delayed item"
        cpy = self.task.config()
        sim = PeakSimulator(**cpy).events
        def _gen():
            yield sim(cpy['nbeads'], cpy['ncycles'], cpy['seed'])

        args.apply(_gen(), levels = self.levels)
