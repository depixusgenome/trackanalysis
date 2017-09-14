#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task & Processor for subtracting beads from other beads"
from    typing                      import List, Iterable
from    functools                   import partial

import  numpy                       as     np
from    utils                       import initdefaults
from    model                       import Task, Level
from    control.processor           import Processor
from    signalfilter.noisereduction import Filter

class SignalAverage:
    "creates an average of signals"
    filter: Filter = None
    @initdefaults(frozenset(locals()))
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
    level                = Level.none
    beads: List[int] = []
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self)

class BeadSubtractionProcessor(Processor):
    "Processor for subtracting beads"
    @staticmethod
    def __action(task, cache, frame, info):
        key = info[1] if isinstance(info[0], tuple) else None
        sub = None if cache is None else cache.get(key, None)
        if sub is None:
            if key is None:
                sub = task([frame.data[i] for i in task.beads])
            else:
                sub = task([frame.data[i, key] for i in task.beads])
            cache[key] = sub

        info[1][:len(sub)] -= sub[:len(info[1])]
        return info

    @classmethod
    def __run(cls, task, cache, frame):
        frame = frame.new().discarding(task.beads)
        return frame.withaction(partial(cls.__action, task, cache))

    @classmethod
    def apply(cls, toframe = None, cache = None, **kwa):
        "applies the subtraction to the frame"
        task = cls.tasktype(**kwa) # pylint: disable=not-callable
        fcn  = partial(cls.__run, task, cache)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        cache = args.data.setCacheDefault(self, {})
        args.apply(self.apply(cache =  cache, **self.config()))

    def beads(self, _, selected: Iterable[int]) -> Iterable[int]:
        "Beads selected/discarded by the task"
        sub = self.task.beads
        return (i for i in selected if i not in sub)
