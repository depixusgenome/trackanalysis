#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task & Processor for subtracting beads from other beads"
from    typing              import (List,   # pylint: disable=unused-import
                                    Optional)
from    functools           import partial

import  numpy               as     np
from    utils               import initdefaults
from    model               import Task, Level
from    control.processor   import Processor
from   .noisereduction      import Filter   # pylint: disable=unused-import

class SignalAverage:
    "creates an average of signals"
    filter = None # type: Optional[Filter]
    @initdefaults
    def __init__(self, **kwa):
        pass

    def __call__(self, signals):
        if len(signals) == 0:
            return 0.

        if len(signals) == 1:
            res = signals[0] if callable(self.filter) else np.copy(signals[0])
        else:
            res  = np.empty(max(len(i) for i in signals), dtype = 'f4')
            ini  = 0
            while len(signals):
                minv = min(len(i) for i in signals)
                np.nanmean([i[ini:minv] for i in signals],
                           axis = 0, out = res[ini:minv])
                signals = [i for i in signals if len(i) > minv]
                ini     = minv

        if callable(self.filter):
            return self.filter(res) # pylint: disable=not-callable
        return res

class BeadSubtractionTask(SignalAverage, Task):
    "Task for subtracting beads"
    level = Level.bead
    beads = [] # type: List[int]
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self)

class BeadSubtractionProcessor(Processor):
    "Processor for subtracting beads"
    @classmethod
    def apply(cls, frame, cache = None, **kwa):
        "applies the subtraction to the frame"
        if cache is None:
            cache = [None]
        elif len(cache) == 0:
            cache.append(None)

        task = cls.tasktype(**kwa) # pylint: disable=not-callable
        def _beadaction(info, cache = cache):
            if cache[0] is None:
                cache[0] = task([frame[i] for i in task.beads])
            info[1][:len(cache[0])] -= cache[0][:len(info[1])]
            return info
        return frame.new().withaction(_beadaction).discarding(task.beads)

    def run(self, args):
        args.apply(partial(self.apply, **self.config()))
