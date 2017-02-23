#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processes TrackSimulatorTask"
from control.processor  import Processor
from .task              import (TrackSimulatorTask, EventSimulatorTask,
                                ByPeaksEventSimulatorTask)

class SimulatorMixin:
    u"Processes a simulator task"
    _FCN  = ''

    @staticmethod
    def _generate(sim, items):
        yield sim(*items)

    def run(self, args):
        u"returns a dask delayed item"
        items = tuple(getattr(self.task, name) for name in ('nbeads', 'seed'))
        sim   = getattr(self.caller(), self._FCN)
        args.apply(self._generate(sim, items), levels = self.levels)

class TrackSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes TrackSimulatorTask"
    tasktype = TrackSimulatorTask
    _FCN     = 'beads'

class EventSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes EventSimulatorTask"
    tasktype = EventSimulatorTask
    _FCN     = 'bybeadevents'

class ByPeaksEventSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes EventSimulatorTask"
    tasktype = ByPeaksEventSimulatorTask
    _FCN     = 'bypeakevents'
