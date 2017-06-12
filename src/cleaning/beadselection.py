#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selecting beads"

from    typing              import NamedTuple, Tuple, Union # pylint: disable=unused-import
from    functools           import partial
import  numpy               as     np

from    utils               import initdefaults
from    signalfilter        import nanhfsigma
from    model               import Task, Level, PHASE
from    control.processor   import Processor

RESULTS  = NamedTuple('Results', [('isvalid', bool), ('noisy', int), ('collapsed', int)])
class BeadSelection:
    "bead selection"
    minsigma = 1e-4
    maxsigma = 1e-2
    ncycles  = 50
    minsize  = .5

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __call__(self, cycs: np.array) -> RESULTS:
        "whether there are enough cycles"
        sigmas     = np.array([nanhfsigma(i) for i in cycs])
        good       = self.minsigma < sigmas < self.maxsigma
        noisy      = len(good) - good.sum()

        good[good] = np.array([np.nanmax(i) - np.nanmin(i) for i in cycs[good]]) > self.minsize
        collapsed  = len(good) - noisy - good.sum()

        return RESULTS(good.sum() > self.ncycles, noisy, collapsed)

class BeadSelectionTask(BeadSelection, Task):
    "bead selection task"
    level = Level.bead
    start = PHASE.initial
    end   = PHASE.measure
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

class BeadSelectionException(Exception):
    "Exception thrown when a bead is not selected"
    def __init__(self, path, bead, message):
        self.path = path # type: Union[str, Tuple[str]]
        self.bead = bead # type: int
        super().__init__(message, 'warning')

class BeadSelectionProcessor(Processor):
    "Processor for bead selection"
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf) -> RESULTS:
        "returns the result of the beadselection"
        if cache is not None:
            key = (frame.parents, info[0])
            val = cache.get(key, None)
            if val is not None:
                return val

        cycs = np.array(list(frame.track.cycles
                             .withdata({info[0]: info[1]})
                             .withphases(cnf.get('start', cls.tasktype.start),
                                         cnf.get('end',   cls.tasktype.end))
                             .values()),
                        dtype = 'O')
        val  = BeadSelectionTask(**cnf)(cycs)
        if cache is not None:
            cache[key] = val
        return val

    @classmethod
    def apply(cls, toframe = None, cache = None, **cnf):
        "applies the task to a frame or returns a method that will"
        def _compute(frame, info):
            res = cls.compute(frame.track, info, cache = cache, **cnf)
            if res.isvalid:
                return info

            if res.noisy > res.collapsed:
                raise BeadSelectionException(frame.parents, info[0], 'Bead is too noisy')

            raise BeadSelectionException(frame.parents, info[0], 'Bead is fixed')

        fcn = lambda frame: frame.withaction(partial(_compute, frame))
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        cache = args.data.setCacheDefault(self, dict())
        return args.apply(cache = cache, **self.config())
