#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Processes TrackSimulatorTask"
from typing             import Optional
import numpy as np
from utils              import initdefaults, EventsArray
from model.task         import RootTask
from model.level        import Level, PHASE
from control.processor  import Processor
from data.track         import Track
from data.views         import TrackView
from .track             import TrackSimulator
from .bindings          import Experiment

class _SimulatorTask(TrackSimulator):
    u"Class indicating that a track file should be added to memory"
    nbeads: int           = 1
    seed:   Optional[int] = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        RootTask.__init__(self, **kwa) # pylint: disable=non-parent-init-called

class TrackSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake track data each time it is called upon"

class EventSimulatorTask(_SimulatorTask, RootTask):
    u"Class that creates fake event data each time it is called upon"
    ncycles: int = 20
    levelou      = Level.event

class ByPeaksEventSimulatorTask(Experiment, RootTask):
    u"Class that creates fake peak data each time it is called upon"
    nbeads:  int           = 1
    seed:    Optional[int] = None
    ncycles: int           = 20
    levelou                = Level.peak
    @initdefaults(frozenset(locals()) - {'levelou'})
    def __init__(self, **kwa):
        super().__init__(**kwa)
        RootTask.__init__(self, **kwa)

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

class TrackSimulatorProcessor(SimulatorMixin, Processor[TrackSimulatorTask]):
    u"Processes TrackSimulatorTask"
    _FCN     = 'beads'

class EventSimulatorProcessor(SimulatorMixin, Processor[EventSimulatorTask]):
    u"Processes EventSimulatorTask"
    _FCN     = 'bybeadevents'

class _PeakGenerator:
    def __init__(self, track, beadid, bead):
        self.track  = track
        self.bead   = bead
        self.beadid = beadid
        self.peaks  = [np.any(i) for i in (track.truth[beadid].events > 0).T]
        self.inds   = track.phase.select(..., PHASE.measure)
        self.ends   = self.inds[:,None] + np.int32(np.cumsum(track.truth[beadid].events, 1))
        self.cur    = 0

    def __iter__(self):
        return self

    def __next__(self):
        from peakfinding.peaksarray import PeaksArray
        if self.cur == 0:
            starts = self.ends[:,-1]
            lasts  = self.track.phase.select(..., PHASE.measure+1)
        else:
            ind    = self.cur
            for k in range(len(self.peaks)-1, -1, -1):
                if self.peaks[k]:
                    ind -= 1
                else:
                    continue
                if ind == 0:
                    lasts  = self.ends[:,k]
                    starts = self.inds if k == 0 else self.ends[:,k-1]
                    break
            else:
                raise StopIteration()

        evts   = [self.bead[i:j] for i, j in zip(starts, lasts)]
        pks    = np.empty(len(evts), dtype = 'O').view(PeaksArray)
        pks[:] = [EventsArray([(i, j)] if len(j) else [])
                  for i, j in zip(starts-self.inds, evts)]
        self.cur += 1
        return (np.nanmean(np.concatenate(evts)), pks)

class ByPeaksEventSimulatorProcessor(Processor[ByPeaksEventSimulatorTask]):
    "Processes EventSimulatorTask"
    @classmethod
    def generate(cls, **cnf):
        "generate a view containing"
        experiment  = cls.tasktype(**cnf)
        data        = experiment.track(seed   = experiment.seed,
                                       nbeads = experiment.nbeads)
        track       = Track(**data)
        track.truth = data['truth']
        return (TrackView(track = track, data = track.beads, level = Level.peak)
                .withaction(cls._action))

    def run(self, args):
        "returns a dask delayed item"
        args.apply((self.generate(**self.config()) for i in range(1)), levels = self.levels)

    @staticmethod
    def canpool():
        """
        This is to stop *pooledinput* from generating the data on multiple machines.
        """
        return True

    @staticmethod
    def _action(frame, info):
        return info[0], _PeakGenerator(frame.track, info[0], info[1])
