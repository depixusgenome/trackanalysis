#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selecting beads"
from    typing                  import Optional, Dict, Any, List, Tuple, Type
from    itertools               import repeat
from    functools               import partial

import  numpy                   as     np

from    utils                   import initdefaults
from    model                   import Task, Level, PHASE
from    data.views              import BEADKEY
from    control.processor       import Processor
from    .datacleaning           import DataCleaning

class PostAlignmentDataCleaning:
    """
    Remove incorrect points or cycles after the cycles have been aligned

    # `aberrant`
    Removes aberrant values.

    A value at position *n* is aberrant if any:

        *  z[n] < percentile(z, percentiles[0]) - percentilerange
        *  z[n] > percentile(z, percentiles[1]) + percentilerange
    """
    percentiles       = 5., 95.
    percentilerange   = .1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def aberrant(self, bead:np.ndarray, clip = False):
        """
        Removes aberrant values.

        Aberrant values are replaced by:

            * *NaN* if *clip* is true,
            * *maxabsvalue ± median*, whichever is closest, if *clip* is false.

        returns: *True* if the number of remaining values is too low
        """
        fin  = np.isfinite(bead)
        good = bead[fin]
        thr  = (np.percentile(good, self.percentiles)
                + [-self.percentilerange, self.percentilerange])

        if clip:
            good[good < thr[0]] = thr[0]
            good[good > thr[1]] = thr[1]
        else:
            good[good < thr[0]] = np.NaN
            good[good > thr[1]] = np.NaN
        bead[fin] = good

class DataCleaningTask(DataCleaning, Task): # pylint: disable=too-many-ancestors
    "Task for removing incorrect points or cycles or even the whole bead"
    __doc__          = DataCleaning.__doc__
    level            = Level.bead
    hfsigmaphases    = PHASE.measure, PHASE.measure
    populationphases = PHASE.measure, PHASE.measure
    extentphases     = PHASE.initial, PHASE.measure
    saturationphases = PHASE.initial, PHASE.measure
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)

class DataCleaningErrorMessage:
    "creates the error message upon request"
    def __init__(self, stats, cnf:Dict[str,Any], # pylint: disable=too-many-arguments
                 tasktype:Type[DataCleaningTask],
                 beadid: BEADKEY,
                 parents: tuple) -> None:
        self.stats    = stats
        self.config   = cnf
        self.tasktype = tasktype
        self.beadid   = beadid
        self.parents  = parents

    def __str__(self):
        return self.message(self.tasktype, self.stats, **self.config)

    def data(self) -> List[Tuple[Optional[int], str, str]]:
        "returns a message if the test is invalid"
        if self.stats is None:
            pop = self.config.get('minpopulation', self.tasktype.minpopulation)
            return [(None, 'population', '< %d' % pop)]

        stats = {i.name: i  for i in self.stats}
        get1  = lambda i, j: len(getattr(stats[i], j))
        get2  = lambda i, j: self.config.get(j+i, getattr(self.tasktype, j+i))
        msg   = (('saturation', '> %.0f%%', 'max'),
                 ('population', '< %.0f%%', 'min'),
                 ('hfsigma',    '< %.4f',   'min'),
                 ('hfsigma',    '> %.4f',   'max'),
                 ('extent',     '< %.2f',   'min'))

        vals  = ((get1(i[0], i[-1]), i[0], i[1] % get2(i[0], i[-1])) for i in msg)
        return [i for i in vals if i[0]]

    @classmethod
    def message(cls, tasktype, stats, **cnf) -> str:
        "returns a message if the test is invalid"
        if stats is None:
            pop = cnf.get('minpopulation', tasktype.minpopulation)
            return 'has less than %d %% valid points' % pop

        stats = {i.name: i  for i in stats}
        get   = lambda i, j: (len(getattr(stats[i], j)),
                              cnf.get(j+i, getattr(tasktype, j+i)))
        msg   = ('%d cycles: non-closing > %.0f%%' % get('saturation', 'max'),
                 '%d cycles: %%good < %.0f%%'      % get('population', 'min'),
                 '%d cycles: σ[HF] < %.4f'         % get('hfsigma',    'min'),
                 '%d cycles: σ[HF] > %.4f'         % get('hfsigma',    'max'),
                 '%d cycles: Δz < %.2f'            % get('extent',     'min'))

        return '\n'.join(i for i in msg if i[0] != '0')

class DataCleaningException(Exception):
    "Exception thrown when a bead is not selected"
    @classmethod
    def create(cls, stats, cnf, tasktype, beadid, parents): # pylint: disable=too-many-arguments
        "creates the exception"
        return cls(DataCleaningErrorMessage(stats, cnf, tasktype, beadid, parents),
                   'warning')

class DataCleaningProcessor(Processor[DataCleaningTask]):
    "Processor for cleaning the data"
    @classmethod
    def __get(cls, name, cnf):
        return cnf.get(name, getattr(cls.tasktype, name))

    @classmethod
    def __test(cls, frame, cnf):
        sel = cls.tasktype(**cnf)
        for name in sel.CYCLES:
            cycs = tuple(frame.withphases(*cls.__get(name+'phases', cnf)).values())
            yield getattr(sel, name)(cycs)

        init = list(frame.withphases(cls.__get('saturationphases', cnf)[0]).values())
        meas = list(frame.withphases(cls.__get('saturationphases', cnf)[1]).values())
        yield sel.saturation(init, meas)

    @classmethod
    def _compute(cls, cnf, frame, info):
        res = cls.compute(frame, info, **cnf)
        if res is None:
            return info
        raise res

    @classmethod
    def saturation(cls, cycs, **cnf):
        "return the saturation count"
        initials = list(cycs.withphases(PHASE.initial).values())
        measures = list(cycs.withphases(PHASE.measure).values())
        return cls.tasktype(**cnf).saturation(initials, measures)

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf) -> Optional[DataCleaningException]:
        "returns the result of the beadselection"
        tested = False
        if cache is not None:
            val, discard = cache.get(info[0], ('', False))
            if discard:
                return DataCleaningException.create(val, cnf, cls.tasktype, info, frame.parents)
            tested       = val != ''

        discard = DataCleaning(**cnf).aberrant(info[1])
        if not tested:
            cycs = frame.track.view("cycles", data = {info[0]: info[1]})
            val  = tuple(cls.__test(cycs, cnf))

        if not discard:
            bad = cls.tasktype.badcycles(val) # type: ignore
            if len(bad):
                for _, cyc in frame.track.view("cycles",
                                               data     = {info[0]: info[1]},
                                               selected = zip(repeat(info[0]), bad)):
                    cyc[:] = np.NaN

                if not tested:
                    minpop  = 1.-cls.__get('minpopulation', cnf)*1e-2
                    discard = np.isnan(info[1]).sum() > len(info[1]) * minpop

        if not (tested or cache is None):
            cache[info[0]] = val, discard
        if discard:
            return DataCleaningException.create(val, cnf, cls.tasktype, info[0], frame.parents)
        return None

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        return toframe.withaction(partial(cls._compute, cnf))

    def run(self, args):
        "updates the frames"
        cache = args.data.setCacheDefault(self, dict())
        return args.apply(partial(self.apply, cache = cache, **self.config()))
