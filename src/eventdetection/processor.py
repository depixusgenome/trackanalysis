#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from   typing             import Optional # pylint: disable=unused-import
from   functools          import partial

import numpy              as     np
from   utils              import initdefaults
from   model              import Task, Level, PHASE
from   control.processor  import Processor

from   .data              import Events
from   .alignment         import ExtremumAlignment
from   .                  import EventDetectionConfig

class ExtremumAlignmentTask(Task):
    """
    Task for aligning on a given phase.

    If no phase is selected, alignment is performed on phase 1 for all then
    phase 3 for outliers.
    """
    level   = Level.bead
    binsize = 5
    factor  = 2.5
    phase   = None # type: Optional[int]
    @initdefaults('binsize', 'phase')
    def __init__(self, **_):
        super().__init__()

class ExtremumAlignmentProcessor(Processor):
    "Aligns cycles to zero"
    class _Utils:
        "Aligns cycles to zero"
        def __init__(self, frame, info):
            "returns computed cycles for this bead"
            self.cycles = frame[info[0],...].new(data = {info[0]: info[1]})

        def bias(self, phase, binsize, subtract):
            "aligns a phase"
            mode  = 'max' if phase == PHASE.pull else 'min'
            align = ExtremumAlignment(binsize = binsize, mode = mode)
            vals  = np.array(list(self.cycles.withphases(phase).values()), dtype = 'O')
            return align.many(vals, subtract = subtract)

        def translate(self, bias):
            "translates data according to provided biases"
            for val, delta in zip(self.cycles.withphases(...).values(), bias):
                if np.isfinite(delta):
                    val += delta
            return next(iter(self.cycles.data.items()))

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        phase   = kwa.get('phase',   cls.tasktype.phase)
        binsize = kwa.get('binsize', cls.tasktype.binsize)
        factor  = kwa.get('factor',  cls.tasktype.factor)
        if phase is None:
            attr   = factor
            action = cls.__apply_best
        else:
            attr   = phase
            action = cls.__apply_onephase

        def _apply(frame):
            return frame.withaction(partial(action, attr, binsize, frame),
                                    beadsonly = True)
        return _apply if toframe is None else _apply(toframe)

    @classmethod
    def __apply_best(cls, factor, binsize, frame, info):
        "applies the task to a frame or returns a function that does so"
        cycles = cls._Utils(frame, info)
        bias   = cycles.bias(PHASE.initial, binsize, True)

        maxes  = cycles.bias(PHASE.pull,    binsize, False) + bias
        maxes -= np.median(maxes)

        bad        = maxes > np.median(np.abs(maxes))*factor
        bias[bad] += maxes[bad]

        return cycles.translate(bias)

    @classmethod
    def __apply_onephase(cls, phase, binsize, frame, info):
        cycles = cls._Utils(frame, info)
        bias   = cycles.bias(phase, binsize, True)
        return cycles.translate(bias)

    def run(self, args):
        args.apply(self.apply(**self.config()))

class EventDetectionTask(EventDetectionConfig, Task):
    "Config for an event detection"
    levelin = Level.bead
    levelou = Level.event
    phase   = PHASE.measure
    @initdefaults('phase')
    def __init__(self, **kw) -> None:
        EventDetectionConfig.__init__(self, **kw)
        Task.__init__(self)

class EventDetectionProcessor(Processor):
    "Generates output from a _tasks."
    @classmethod
    def apply(cls, toframe, **kwa):
        "applies the task to a frame or returns a function that does so"
        kwa['first'] = kwa['last'] = kwa.pop('phase')
        fcn = lambda data: Events(track = data.track, data = data, **kwa)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "iterates through beads and yields cycle events"
        args.apply(self.apply(None, **self.task.config()), levels = self.levels)
