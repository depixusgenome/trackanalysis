#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Task & Processor for subtracting beads from other beads"
from   typing                       import List, Iterable, Union, Dict, cast
from   functools                    import partial
from   itertools                    import repeat

import numpy                        as     np

from   taskcontrol.processor        import Processor
from   data.views                   import Cycles, Beads
from   taskmodel                    import Task, Level
from   signalfilter.noisereduction  import Filter
from   utils                        import initdefaults
from   ..beadsubtraction            import aggtype, SubtractMedianSignal, AggType
# pylint: disable=import-error
from   .._core                      import constant as _cleaningcst

class BeadSubtractionTask(Task):
    """
    Task for subtracting an average signal from beads.

    Stretches of constant values are also removed prior to the subtraction.
    See `AberrantValuesRule` for a documentation.
    """
    filter: Filter    = None
    beads:  List[int] = []
    agg:    AggType   = SubtractMedianSignal()
    mindeltavalue     = 1e-6
    mindeltarange     = 3
    level             = Level.none
    def __delayed_init__(self, _):
        if isinstance(self.agg, str):
            self.agg = aggtype(self.agg)

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)

class BeadSubtractionProcessor(Processor[BeadSubtractionTask]):
    "Processor for subtracting beads"
    @classmethod
    def _action(cls, task, cache, frame, info):
        key = info[0][1] if isinstance(info[0], tuple) else None
        sub = None if cache is None else cache.get(key, None)
        if sub is None:
            sub = cls(task = task).signal(frame, key)
            if cache is not None:
                cache[key] = sub

        out             = np.copy(info[1])
        _cleaningcst(task, out)
        out[:len(sub)] -= sub[:len(out)]
        return info[0], out

    @classmethod
    def apply(cls, toframe = None, cache = None, **kwa):
        "applies the subtraction to the frame"
        if toframe is None:
            return partial(cls.apply, cache = cache, **kwa)

        task    = cls.tasktype(**kwa) # pylint: disable=not-callable
        if len(task.beads) == 0:
            return toframe

        toframe = toframe.new().discarding(task.beads)
        return toframe.withaction(partial(cls._action, task, cache))

    def run(self, args):
        "updates frames"
        cache = args.data.setcachedefault(self, {})
        args.apply(self.apply(cache =  cache, **self.config()))

    def beads(self, _, selected: Iterable[int]) -> Iterable[int]: # type: ignore
        "Beads selected/discarded by the task"
        sub = self.task.beads
        return (i for i in selected if i not in sub)

    def signal(self, frame: Union[Beads, Cycles], key = None) -> np.ndarray:
        "returns the signal to subtract from beads"
        task  = self.task

        next(iter(frame.keys())) # unlazyfy # type: ignore
        data = cast(Dict, frame.data)
        itr  = (cast(Iterable[int], task.beads) if key is None else
                cast(Iterable[int], list(zip(task.beads, repeat(key)))))
        if len(task.beads) == 0:
            sub = 0.

        elif len(task.beads) == 1:
            sub = np.copy(data[task.beads[0]])

        else:
            sub = task.agg.process(itr, frame)

        return task.filter(sub) if task.filter else sub
