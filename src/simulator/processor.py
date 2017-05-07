#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processes TrackSimulatorTask"
from typing             import Optional     # pylint: disable=unused-import
from utils              import initdefaults
from model.task         import RootTask, Level
from control.processor  import Processor
from .track             import TrackSimulator

class _SimulatorTask(TrackSimulator):
    u"Class indicating that a track file should be added to memory"
    nbeads = 1      # type: int
    seed   = None   # type: Optional[int]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        RootTask.__init__(self, **kwa) # pylint: disable=non-parent-init-called

class TrackSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake track data each time it is called upon"

class EventSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake event data each time it is called upon"
    ncycles = 20    # type: int
    levelou = Level.event

class ByPeaksEventSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake peak data each time it is called upon"
    ncycles = 20    # type: int
    levelou = Level.peak

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

    @staticmethod
    def canpool():
        """
        This is to stop *pooledinput* from generating the data on multiple machines.
        """
        return True

class TrackSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes TrackSimulatorTask"
    _FCN     = 'beads'

class EventSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes EventSimulatorTask"
    _FCN     = 'bybeadevents'

class ByPeaksEventSimulatorProcessor(SimulatorMixin, Processor):
    u"Processes EventSimulatorTask"
    _FCN     = 'bypeakevents'
