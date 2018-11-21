#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all cleaning related tasks"
from   functools          import partial
from   typing             import Optional
import numpy              as     np
from   data               import Track
from   model.level        import Level, PHASE
from   model.task         import Task
from   control.processor  import Processor
from   utils              import initdefaults

class ClippingTask(Task):
    "Task discarding phase 5 data below phase 1 or above phase 3"
    level       = Level.bead
    lowfactor   = 4.
    highfactor  = 0.
    low         = PHASE.initial
    high        = PHASE.pull
    correction  = PHASE.measure
    replacement = np.NaN

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

    def minthreshold(self, track:Track, key:int, data: np.ndarray) -> Optional[float]:
        "return the min threshold"
        if self.lowfactor is None or self.lowfactor <= 0.:
            return None
        hfs = track.rawprecision(key)
        return track.phaseposition(self.low,  data)-hfs*self.lowfactor

    def maxthreshold(self, track:Track, key:int, data: np.ndarray) -> Optional[float]:
        "return the min threshold"
        if self.highfactor is None or self.highfactor <= 0.:
            return None
        hfs = track.rawprecision(key)
        return track.phaseposition(self.high, data)+hfs*self.highfactor

    def __call__(self, track:Track, key:int, data: np.ndarray):
        maxv = self.maxthreshold(track, key, data)
        minv = self.minthreshold(track, key, data)
        if minv is None and maxv is None:
            return

        pha  = track.phase.select(..., [self.correction, self.correction+1]).ravel()
        itms = np.split(data, pha)[1::2]
        if minv is None and maxv is not None:
            for i in itms:
                i[~np.isfinite(i)] = maxv+1
                i[(i > maxv)]      = self.replacement

        elif maxv is None and minv is not None:
            for i in itms:
                i[~np.isfinite(i)] = minv-1
                i[(i < minv)]      = self.replacement

        elif maxv is not None and minv is not None:
            for i in itms:
                i[~np.isfinite(i)]         = maxv+1
                i[(i < minv) | (i > maxv)] = self.replacement

class ClippingProcessor(Processor[ClippingTask]):
    "Processor for cleaning the data"
    @staticmethod
    def action(task, frame, info):
        "action of clipping"
        task(frame.track, *info)
        return info

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        if toframe is None:
            return partial(cls.apply, **cnf)
        return toframe.withaction(partial(cls.action, ClippingTask(**cnf)))

    def run(self, args):
        "updates the frames"
        return args.apply(partial(self.apply, **self.config()))
