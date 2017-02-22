#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processes TrackSimulatorTask"
from control.processor  import Processor
from .task              import TrackSimulatorTask, EventSimulatorTask, PeakSimulatorTask
from .track             import TrackSimulator
from .peak              import PeakSimulator

class SimulatorMixin:
    u"Processes a simulator task"
    _ARGS = ('nbeads', 'seed')
    @staticmethod
    def _simulator(kwa):
        raise NotImplementedError()

    @staticmethod
    def _generate(sim, items):
        yield sim(*items)

    def run(self, args):
        u"returns a dask delayed item"
        items = tuple(getattr(self.task, name) for name in self._ARGS)
        sim   = self._simulator(self.config())
        args.apply(self._generate(sim, items), levels = self.levels)

class TrackSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes TrackSimulatorTask"
    tasktype = TrackSimulatorTask
    @staticmethod
    def _simulator(kwa):
        return TrackSimulator(**kwa).track

    @staticmethod
    def _generate(sim, items):
        yield sim(*items).beads

class EventSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes EventSimulatorTask"
    _ARGS    = ('nbeads', 'ncycles', 'seed')
    tasktype = EventSimulatorTask
    @staticmethod
    def _simulator(kwa):
        return PeakSimulator(**kwa).events

class PeakSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes EventSimulatorTask"
    _ARGS    = ('nbeads', 'ncycles', 'seed')
    tasktype = PeakSimulatorTask
    @staticmethod
    def _simulator(kwa):
        return PeakSimulator(**kwa).groupedbypeaks
