#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selecting beads"

from    typing                  import (Optional, NamedTuple, Dict, Any, List,
                                        Tuple, Type)
from    abc                     import ABC, abstractmethod
from    itertools               import repeat
from    functools               import partial

import  numpy                   as     np
from    numpy.lib.stride_tricks import as_strided

from    utils                   import initdefaults
from    signalfilter            import nanhfsigma
from    model                   import Task, Level, PHASE
from    data.views              import BEADKEY
from    control.processor       import Processor
from    ._core                  import (constant as _cleaningcst, # pylint: disable=import-error
                                        clip     as _cleaningclip)

Partial = NamedTuple('Partial',
                     [('name', str),
                      ('min', np.ndarray),
                      ('max', np.ndarray),
                      ('values', np.ndarray)])

class NaNDensity(ABC):
    "removes frames affected by NaN value in their neighborhood"
    @staticmethod
    def _countnans(bead, width, cnt):
        tmp = np.asarray(np.isnan(bead), dtype = 'i1')
        if width > 1:
            tmp = np.sum(as_strided(tmp,
                                    strides = (tmp.strides[0], tmp.strides[0]),
                                    shape   = (tmp.size-width+1, width)),
                         axis = 1) >= cnt
        return tmp

    @abstractmethod
    def apply(self, bead:np.ndarray) -> None:
        "removes bad frames"

class LocalNaNPopulation(NaNDensity):
    "Removes frames which have NaN values to their right and their left"
    window = 5
    ratio  = 20
    @initdefaults
    def __init__(self, **_):
        super().__init__()

    def apply(self, bead: np.ndarray):
        "Removes frames which have NaN values to their right and their left"
        tmp = self._countnans(bead, self.window, self.ratio/100.*self.window)
        tmp = np.logical_and(tmp[:-self.window-1], tmp[self.window+1:])
        bead[self.window:-self.window][tmp] = np.NaN

class DerivateIslands(NaNDensity):
    """
    Removes frame intervals with the following characteristics:

    * there are *islandwidth* or less good values in a row,
    * with a derivate of at least *maxderivate*
    * surrounded by *riverwidth* or more NaN values in a row on both sides
    """
    riverwidth  = 2
    islandwidth = 10
    ratio       = 80
    maxderivate = .1
    @initdefaults
    def __init__(self, **_):
        super().__init__()

    def apply(self, bead: np.ndarray):
        "Removes frames which have NaN values to their right and their left"
        tmp = np.nonzero(self._countnans(bead, self.riverwidth, self.riverwidth))[0]
        if len(tmp) == 0:
            return

        left  = np.setdiff1d(tmp, tmp-1)+self.riverwidth

        right = np.setdiff1d(tmp, tmp+1)
        right = right[np.searchsorted(right, left[0]):]

        rinds = np.searchsorted(left, right)

        good  = right-left[rinds-1] <= self.islandwidth
        if good.sum() == 0:
            return

        mder = self.maxderivate
        for ileft, iright in zip(left[rinds[good]-1], right[good]):
            cur  = bead[ileft:iright]
            vals = cur[np.isfinite(cur)]
            if len(vals) < 3:
                cur[:] = np.NaN
                continue

            cnt = self.ratio*1e-2*(len(vals)-2)
            if (np.abs(vals[1:-1]-vals[:-2]*.5-vals[2:]*.5) > mder).sum() >= cnt:
                cur[:] = np.NaN

class DataCleaning:
    "bead selection"
    mindeltavalue                = 1e-6
    mindeltarange                = 3
    nandensity: List[NaNDensity] = [LocalNaNPopulation(window = 16, ratio = 50),
                                    DerivateIslands()]
    maxabsvalue                  = 5.
    maxderivate                  = .6
    minpopulation                = 80.
    minhfsigma                   = 1e-4
    maxhfsigma                   = 1e-2
    minextent                    = .5
    __ZERO                       = np.zeros(0, dtype = 'i4')

    CYCLES                       = 'hfsigma', 'extent', 'population'

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __test(self, name, test:list) -> Partial:
        test = np.asarray(test, 'f4')
        low  = np.nonzero(test <= getattr(self, 'min'+name))[0]
        if hasattr(self, 'max'+name):
            high = np.nonzero(test >= getattr(self, 'max'+name))[0]
        else:
            high = self.__ZERO
        return Partial(name, low, high, test)

    @staticmethod
    def badcycles(stats) -> np.ndarray:
        "returns all bad cycles"
        bad = np.empty(0, dtype = 'i4')
        if stats is None:
            return bad
        for stat in stats.values() if isinstance(stats, dict) else stats:
            bad = np.union1d(bad, stat.min)
            bad = np.union1d(bad, stat.max)
        return bad

    def hfsigma(self, cycs: np.ndarray) -> Partial:
        "computes noisy cycles"
        return self.__test('hfsigma', [nanhfsigma(i) for i in cycs])

    def extent(self, cycs: np.ndarray) -> Partial:
        "computes too short or too long cycles"
        maxv = np.finfo('f4').max
        test = [np.nanmax(i)-np.nanmin(i) if any(np.isfinite(i)) else maxv for i in cycs]
        return self.__test('extent', test)

    def population(self, cycs: np.ndarray) -> Partial:
        "computes too short or too long cycles"
        test = [ 0. if len(i) == 0 else np.isfinite(i).sum()/len(i)*100. for i in cycs]
        return self.__test('population', test)

    def localpopulation(self, bead:np.ndarray):
        "Removes values which have too few good neighbours"
        for itm in self.nandensity:
            itm.apply(bead)

    def aberrant(self, bead:np.ndarray, clip = False) -> bool:
        """
        Removes aberrant values.

        A value at position *n* is aberrant if any:

        * |z[n] - median(z)| > maxabsvalue
        * |(z[n+1]-z[n-1])/2-z[n]| > maxderivate
        * |z[I-mindeltarange+1] - z[I-mindeltarange+2] | < mindeltavalue
          && ...
          && |z[I-mindeltarange+1] - z[I]|               < mindeltavalue
          && n ∈ [I-mindeltarange+2, I]
        * #{z[I-nanwindow//2:I+nanwindow//2] is nan} < nanratio*nanwindow

        Aberrant values are replaced by:

        * *NaN* if *clip* is true,
        * *maxabsvalue ± median*, whichever is closest, if *clip* is false.

        returns: *True* if the number of remaining values is too low
        """
        _cleaningclip(self, clip, np.nanmedian(bead), bead)
        _cleaningcst(self, bead)
        self.localpopulation(bead)
        return np.isfinite(bead).sum() <= len(bead) * self.minpopulation * 1e-2

class PostAlignmentDataCleaning:
    "bead selection"
    percentiles       = 5., 95.
    percentilerange   = .1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def aberrant(self, bead:np.ndarray, clip = False):
        """
        Removes aberrant values.

        A value at position *n* is aberrant if any:

            *  z[n] < percentile(z, percentiles[0]) - percentilerange
            *  z[n] > percentile(z, percentiles[1]) + percentilerange

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
        msg   = (('population', '< %.0f%%', 'min'),
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
        msg   = ('%d cycles: %%good < %.0f%%'      % get('population', 'min'),
                 '%d cycles: σ[HF] < %.4f'         % get('hfsigma',    'min'),
                 '%d cycles: σ[HF] > %.4f'         % get('hfsigma',    'max'),
                 '%d cycles: Δz < %.2f' % get('extent',     'min'))

        return '\n'.join(i for i in msg if i[0] != '0')

class DataCleaningException(Exception):
    "Exception thrown when a bead is not selected"
    @classmethod
    def create(cls, stats, cnf, tasktype, beadid, parents): # pylint: disable=too-many-arguments
        "creates the exception"
        return cls(DataCleaningErrorMessage(stats, cnf, tasktype, beadid, parents),
                   'warning')

class DataCleaningProcessor(Processor[DataCleaningTask]):
    "Processor for bead selection"
    @classmethod
    def __get(cls, name, cnf):
        return cnf.get(name, getattr(cls.tasktype, name))

    @classmethod
    def __test(cls, frame, cnf):
        sel = cls.tasktype(**cnf)
        for name in sel.CYCLES:
            cycs = tuple(frame.withphases(*cls.__get(name+'phases', cnf)).values())
            yield getattr(sel, name)(cycs)

    @classmethod
    def _compute(cls, cnf, frame, info):
        res = cls.compute(frame, info, **cnf)
        if res is None:
            return info
        raise res

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
                    discard = not tested and np.isnan(info[1]).sum() > len(info[1]) * minpop
            elif not tested:
                discard = False

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
