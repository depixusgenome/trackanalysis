#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   functools              import partial

import numpy                  as     np
from   taskcontrol.processor  import Processor
from   taskmodel              import Task, Level, PHASE
from   utils                  import initdefaults

class BiasRemovalTask(Task, zattributes = ('zerodelta', 'binsize')):
    "removes the bias from the whole bead"
    level       = Level.bead
    phase       = PHASE.measure
    length      = 10
    zeropos     = 5.
    zerodelta   = 1e-2
    binsize     = 1e-3

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class BiasRemovalProcessor(Processor[BiasRemovalTask]):
    "removes the bias from the whole bead"
    @staticmethod
    def beadaction(task, frame, info):
        "removes the bias"
        cycles = (frame.new(data = dict((info,)))
                  [info[0],...]
                  .withphases(task.phase))
        vals   = np.concatenate([i[-task.length:] for i in cycles.values()])
        vals   = vals[np.isfinite(vals)]
        zero   = np.percentile(vals, task.zeropos)
        vals   = vals[np.abs(vals-zero) < task.zerodelta]

        hist, bins  = np.histogram(vals,
                                   int(task.zerodelta/task.binsize+0.5),
                                   (zero-task.zerodelta, zero+task.zerodelta))
        bias        = bins[np.argmax(hist):][:2].mean()
        info[1][:] -= bias
        return info

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        if toframe is None:
            return cls.apply
        task = cls.tasktype(**cnf) # pylint: disable=not-callable
        return toframe.withaction(partial(cls.beadaction, task))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))
