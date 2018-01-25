#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Removing aberrant points and cycles"
import  warnings
from    typing                  import NamedTuple, List
from    abc                     import ABC, abstractmethod

import  numpy                   as     np
from    numpy.lib.stride_tricks import as_strided

from    utils                   import initdefaults
from    signalfilter            import nanhfsigma
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

_ZERO = np.zeros(0, dtype = 'i4')
class DataCleaningRule:
    "Base for cleaning"
    def _test(self, name, test:list) -> Partial:
        test = np.asarray(test, 'f4')
        low  = np.nonzero(test <= getattr(self, 'min'+name))[0]
        if hasattr(self, 'max'+name):
            high = np.nonzero(test >= getattr(self, 'max'+name))[0]
        else:
            high = _ZERO
        return Partial(name, low, high, test)

class AberrantValuesRule:
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

    """
    mindeltavalue                = 1e-6
    mindeltarange                = 3
    nandensity: List[NaNDensity] = [LocalNaNPopulation(window = 16, ratio = 50),
                                    DerivateIslands()]
    maxabsvalue                  = 5.
    maxderivate                  = .6
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def aberrant(self, bead:np.ndarray, clip = False):
        """
        Removes aberrant values.

        Aberrant values are replaced by:

        * `NaN` if `clip` is true,
        * `maxabsvalue ± median`, whichever is closest, if `clip` is false.

        returns: *True* if the number of remaining values is too low
        """
        _cleaningclip(self, clip, np.nanmedian(bead), bead)
        _cleaningcst(self, bead)
        self.localpopulation(bead)

    def localpopulation(self, bead:np.ndarray):
        "Removes values which have too few good neighbours"
        for itm in self.nandensity:
            itm.apply(bead)

class HFSigmaRule(DataCleaningRule):
    """
    Remove cycles with too low or too high a variability.

    The variability is measured as the median of the absolute value of the
    pointwise derivate of the signal. The median itself is estimated using the
    P² quantile estimator algorithm.

    Too low a variability is a sign that the tracking algorithm has failed to
    compute a new value and resorted to using a previous one.

    Too high a variability is likely due to high brownian motion amplified by a
    rocking motion of a bead due to the combination of 2 factors:

    1. The bead has a prefered magnetisation axis. This creates a prefered
    horisontal plane and thus a prefered vertical axis.
    2. The hairpin is attached off-center from the vertical axis of the bead.
    """
    minhfsigma = 1e-4
    maxhfsigma = 1e-2
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def hfsigma(self, cycs: np.ndarray) -> Partial:
        """
        Remove cycles with too low or too high a variability
        """
        return self._test('hfsigma', [nanhfsigma(i) for i in cycs])

class MinPopulationRule(DataCleaningRule):
    """
    Remove cycles with too few good points.

    Good points are ones which have not been declared aberrant and which have
    a finite value.
    """
    minpopulation                = 80.
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def population(self, cycs: np.ndarray) -> Partial:
        "computes too short or too long cycles"
        test = [ 0. if len(i) == 0 else np.isfinite(i).sum()/len(i)*100. for i in cycs]
        return self._test('population', test)

class MinExtentRule(DataCleaningRule):
    """
    Remove cycles which don't open.

    That the bead hasn't opened is extracted directly from too low a z range between
    the phases `PHASE.initial` and `PHASE.pull`.
    """
    minextent                    = .5
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    def extent(self, cycs: np.ndarray) -> Partial:
        "computes too short or too long cycles"
        maxv = np.finfo('f4').max
        test = [np.nanmax(i)-np.nanmin(i) if any(np.isfinite(i)) else maxv for i in cycs]
        return self._test('extent', test)

class SaturationRule:
    """
    Remove beads which don't have enough cycles ending at zero.

    When too many cycles (> 90%) never reach 0 before the end of phase 5, the bead is
    discarded. Such a case arises when:

    * the hairpin never closes: the force is too high,
    * a hairpin structure keeps the hairpin from closing. Such structures should be
    detectable in ramp files.
    * an oligo is blocking the loop.
    """
    maxdisttozero = .015
    maxsaturation  = 90.
    satwindow     = 10
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def saturation(self, initials, measures) -> Partial:
        """
        Remove beads which don't have enough cycles ending at zero
        """
        if len(initials) != len(measures):
            raise RuntimeError("There should be as many phase 1 as phase 5")

        window   = self.satwindow
        med      = np.nanmedian
        itr      = zip(initials, measures)
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category = RuntimeWarning,
                                    message = '.*All-NaN slice encountered.*')
            deltas   = np.array([med(j[window:])-med(i) for i, j in itr], dtype = 'f4')

        fin      = np.isfinite(deltas)
        low      = np.zeros(len(deltas), dtype = 'bool')
        low[fin] = deltas[fin] > self.maxdisttozero
        if low.sum() > fin.sum()*(1e-2*self.maxsaturation):
            return Partial('saturation', _ZERO, np.nonzero(low)[0], deltas)
        return Partial('saturation', _ZERO, _ZERO, deltas)

class DataCleaning(AberrantValuesRule,
                   HFSigmaRule,
                   MinPopulationRule,
                   MinExtentRule,
                   SaturationRule):
    """
    Remove specific points, cycles or even the whole bead depending on a number
    of criteria implemented in aptly named methods:

    # `aberrant`
    {}

    # `hfsigma`
    {}

    # `population`
    {}

    # `extent`
    {}

    # `saturation`
    {}
    """
    CYCLES  = 'hfsigma', 'extent', 'population'
    def __init__(self, **_):
        for base in DataCleaning.__bases__:
            base.__init__(self, **_) # type: ignore

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

    def aberrant(self, bead:np.ndarray, clip = False) -> bool:
        super().aberrant(bead, clip)
        return np.isfinite(bead).sum() <= len(bead) * self.minpopulation * 1e-2

DataCleaning.__doc__ = DataCleaning.__doc__.format(*(i.__doc__ for i in DataCleaning.__bases__))
