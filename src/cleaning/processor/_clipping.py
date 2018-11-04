#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"all cleaning related tasks"
from   functools          import partial
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

    def __call__(self, track:Track, key:int, data: np.ndarray):
        hfs  = track.rawprecision(key)
        minv = track.phaseposition(self.low,  data)-hfs*self.lowfactor
        maxv = track.phaseposition(self.high, data)+hfs*self.highfactor
        pha  = track.phase.select(..., [self.correction, self.correction+1])
        for i in np.split(data, pha.ravel())[1::2]:
            i[np.isnan(i)]             = maxv+1
            i[(i < minv) | (i > maxv)] = self.replacement

class ClippingProcessor(Processor[ClippingTask]):
    "Processor for cleaning the data"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        if toframe is None:
            return partial(cls.apply, **cnf)
        task = ClippingTask(**cnf)
        return toframe.withaction(lambda i, j: task(i.track, *j))

    def run(self, args):
        "updates the frames"
        return args.apply(partial(self.apply, **self.config()))
