#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selecting beads"

from    typing                import (Optional, # pylint: disable=unused-import
                                      NamedTuple, Tuple, Union)
from    itertools             import repeat
from    functools             import partial
import  numpy                 as     np
from    scipy.ndimage.filters import correlate1d

from    utils                 import initdefaults
from    signalfilter          import nanhfsigma
from    model                 import Task, Level, PHASE
from    control.processor     import Processor

Partial = NamedTuple('Partial',
                     [('name', str),
                      ('min', np.ndarray),
                      ('max', np.ndarray),
                      ('values', np.ndarray)])

class DataCleaning:
    "bead selection"
    maxabsvalue   = 5.
    maxderivate   = 2.
    minpopulation = 80.
    minhfsigma    = 1e-4
    maxhfsigma    = 1e-2
    minextent     = .5

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __test(self, name, test:list) -> Partial:
        test = np.asarray(test, 'f4')
        low  = np.nonzero(test <= getattr(self, 'min'+name))[0]
        if hasattr(self, 'max'+name):
            high = np.nonzero(test >= getattr(self, 'max'+name))[0]
        else:
            high = np.zeros(0)
        return Partial(name, low, high, test)

    @staticmethod
    def badcycles(stats):
        "returns all bad cycles"
        bad = np.empty(0, dtype = 'i4')
        for stat in stats:
            bad = np.union1d(bad, stat.min)
            bad = np.union1d(bad, stat.max)
        return bad

    def hfsigma(self, cycs: np.ndarray) -> Partial:
        "computes noisy cycles"
        return self.__test('hfsigma', [nanhfsigma(i) for i in cycs])

    def extent(self, cycs: np.ndarray) -> Partial:
        "computes too short or too long cycles"
        test = [np.nanmax(i)-np.nanmin(i) for i in cycs]
        return self.__test('extent', test)

    def population(self, cycs: np.ndarray) -> Partial:
        "computes too short or too long cycles"
        test = [ 0. if len(i) == 0 else np.isfinite(i).sum()/len(i)*100. for i in cycs]
        return self.__test('population', test)

    def aberrant(self, bead:np.ndarray) -> bool:
        "removes aberrant values"
        der = correlate1d([.5, -1., .5], bead, mode = 'nearest')
        bead[np.abs(der)  > self.maxderivate] = np.NaN
        bead[np.abs(bead) < self.maxabsvalue] = np.NaN
        return np.isfinite(bead).sum() <= len(bead) * self.minpopulation * 1e-2

class DataCleaningTask(DataCleaning, Task):
    "bead selection task"
    level            = Level.bead
    hfsigmaphases    = PHASE.measure, PHASE.measure
    populationphases = PHASE.measure, PHASE.measure
    extentphases     = PHASE.initial, PHASE.measure
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

class DataCleaningException(Exception):
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
            if stats is None:
                pop = cnf.get('minpopulation', tasktype.minpopulation)
                return 'has less than %d %% valid points' % pop

            stats = {i.name: i  for i in stats}
            get   = lambda i, j: (len(getattr(stats[i], j)),
                                  cnf.get(j+i, getattr(tasktype, j+i)))
            msg   = ('%d cycles: valid < %.0f%%' % get('population', 'min'),
                     '%d cycles: σ[HF] < %.4f'   % get('hfsigma',    'min'),
                     '%d cycles: σ[HF] > %.4f'   % get('hfsigma',    'max'),
                     '%d cycles: z range > %.2f' % get('extent',     'max'))

            return '\n'.join(i for i in msg if i[0] != '0')

    def __init__(self, tasktype, stats, **cnf):
        super().__init__(self.ErrorMessage(tasktype, stats, cnf), 'warning')

    @classmethod
    def test(cls, tasktype, stats, **cnf) -> Optional['DataCleaningException']:
        "creates a DataCleaningException if needed"
        bad = tasktype.badcycles(stats)
        if len(bad) < cnf.get('ncycles', getattr(tasktype, 'ncycles')):
            return cls(tasktype, stats, **cnf)
        return bad

class DataCleaningProcessor(Processor):
    "Processor for bead selection"
    @classmethod
    def __get(cls, name, cnf):
        return cnf.get(name, getattr(cls.tasktype, name))

    @classmethod
    def __test(cls, frame, cnf):
        sel = DataCleaningTask(**cnf)
        for name in ('population', 'hfsigma', 'extent'):
            cycs = tuple(frame.withphases(*cls.__get(name+'phases', cnf)).values())
            yield getattr(sel, name)(cycs)

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf) -> Tuple[Partial]:
        "returns the result of the beadselection"
        if cache is not None:
            key = (frame.parents, info[0])
            val = cache.get(key, '')
            if val is None:
                return None

            if val == '':
                DataCleaning(**cnf).aberrant(info[1])
                return val

        if DataCleaning(**cnf).aberrant(info[1]):
            val = None
        else:
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
            msg = DataCleaningException.test(cls.tasktype, res, **cnf)
            if isinstance(msg, Exception):
                raise msg

            for _, val in (frame.track.cycles
                           .withdata({info[0]: info[1]})
                           .selecting(zip(repeat(info[0]), msg))):
                val[:] = np.NaN
            return info

        fcn = lambda frame: frame.withaction(partial(_compute, frame))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        cache = args.data.setCacheDefault(self, dict())
        return args.apply(cache = cache, **self.config())
