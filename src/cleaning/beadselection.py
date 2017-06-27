#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selecting beads"

from    typing              import (Optional, # pylint: disable=unused-import
                                    NamedTuple, Tuple, Union)
from    functools           import partial
import  numpy               as     np

from    utils               import initdefaults
from    signalfilter        import nanhfsigma
from    model               import Task, Level, PHASE
from    control.processor   import Processor

PARTIAL = NamedTuple('Partial', [('name', str), ('good', np.ndarray), ('min', int), ('max', int)])
class BeadSelection:
    "bead selection"
    minhfsigma  = 1e-4
    maxhfsigma  = 1e-2
    population  = 99.
    minextent   = .5
    maxextent   = 5.

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __test(self, name, test:list, good: np.ndarray = None) -> PARTIAL:
        test   = np.array(test, 'f4')
        ngood  = len(test) if good is None else good.sum()
        np.less(getattr(self, 'min'+name), test, out = good)
        low    = ngood - good.sum()
        np.less(test, getattr(self, 'max'+name), out = good)
        return PARTIAL(name, good, low, ngood - low - good.sum() )

    def hfsigma(self, cycs: np.ndarray, good: np.ndarray = None) -> PARTIAL:
        "computes noisy cycles"
        return self.__test('hfsigma', [nanhfsigma(i) for i in cycs], good)

    def extent(self, cycs: np.ndarray, good: np.ndarray = None) -> PARTIAL:
        "computes too short or too long cycles"
        test = [np.nanmax(i)-np.nanmin(i) for i in cycs]
        return self.__test('extent', test, good)

class BeadSelectionTask(BeadSelection, Task):
    "bead selection task"
    level         = Level.bead
    hfsigmaphases = PHASE.measure, PHASE.measure
    extentphases  = PHASE.initial, PHASE.measure
    mincycles     = 50
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

class BeadSelectionException(Exception):
    "Exception thrown when a bead is not selected"
    class ErrorMessage:
        "creates the error message upon request"
        def __init__(self, stats, cnf, tasktype):
            self.stats    = stats
            self.config   = cnf
            self.tasktype = tasktype

        def __str__(self):
            return self.message(self.tasktype, self.stats, **self.config)

        @classmethod
        def message(cls, tasktype, stats, **cnf) -> str:
            "returns a message if the test is invalid"
            stats = {i.name: i  for i in stats}
            get   = lambda i, j: (getattr(stats[i], j),
                                  cnf.get(j+i, getattr(tasktype, j+i)))
            msg   = ('%d cycles: σ[HF] < %.4f'   % get('hfsigma', 'min'),
                     '%d cycles: σ[HF] > %.4f'   % get('hfsigma', 'max'),
                     '%d cycles: z range < %.2f' % get('extent', 'min'),
                     '%d cycles: z range > %.2f' % get('extent', 'max'))

            return '\n'.join(i for i in msg if i[0] != '0')

    def __init__(self, tasktype, stats, **cnf):
        super().__init__(self.ErrorMessage(tasktype, stats, cnf), 'warning')

    @classmethod
    def test(cls, tasktype, stats, **cnf) -> Optional['BeadSelectionException']:
        "creates a BeadSelectionException if needed"
        if stats[-1].good.sum() < cnf.get('ncycles', getattr(tasktype, 'ncycles')):
            return cls(tasktype, stats, **cnf)
        return None

class BeadSelectionProcessor(Processor):
    "Processor for bead selection"
    @classmethod
    def __get(cls, name, cnf):
        return cnf.get(name, getattr(cls.tasktype, name))

    @classmethod
    def __test(cls, frame, cnf):
        sel  = BeadSelectionTask(**cnf)
        good = None
        for name in 'hfsigma', 'extent':
            cycs = tuple(frame.withphases(*cls.__get(name, cnf)).values())
            out  = getattr(sel, name)(cycs, good = good)
            good = out.good
            yield out

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf) -> Tuple[PARTIAL]:
        "returns the result of the beadselection"
        if cache is not None:
            key = (frame.parents, info[0])
            val = cache.get(key, None)
            if val is not None:
                return val

        cycs = frame.track.cycles.withdata({info[0]: info[1]})
        val  = tuple(cls.__test(cycs, cnf))
        if cache is not None:
            cache[key] = val
        return val

    @classmethod
    def apply(cls, toframe = None, cache = None, **cnf):
        "applies the task to a frame or returns a method that will"
        def _compute(frame, info):
            res = cls.compute(frame.track, info, cache = cache, **cnf)
            msg = BeadSelectionException.test(cls.tasktype, res, **cnf)
            if msg is not None:
                raise msg
            return info

        fcn = lambda frame: frame.withaction(partial(_compute, frame))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        cache = args.data.setCacheDefault(self, dict())
        return args.apply(cache = cache, **self.config())
