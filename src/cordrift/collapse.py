#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Collapse intervals. The idea is to measure the behaviour common to all
stretches of data. This should be removed as it's source is either a (thermal,
electric, ...) drift or a mechanical vibration.
"""
from typing     import (Optional, Union, Sized,     # pylint: disable=unused-import
                        Any, Callable, Iterable, Sequence, cast)
from enum       import Enum
import pandas
import numpy; np = numpy # type: Any # pylint: disable=multiple-statements,invalid-name

class Profile(Sized):
    u"A bead profile: the behaviour common to all stretches of data"
    def __init__(self, inter):
        if isinstance(inter, int):
            self.xmin  = 0
            self.xmax  = inter
        else:
            self.xmin  = min(i[0][0]   for i in inter)
            self.xmax  = max(i[0][-1]  for i in inter)+1

        length     = self.xmax-self.xmin
        self.count = np.zeros((length,), dtype = np.int32)
        self.value = np.zeros((length,), dtype = np.float32)

    def __len__(self):
        return len(self.count)

def _iter_ranges(xmin, inter):
    for rng in inter:
        cur = rng[0] >= xmin
        if not any(cur):
            continue
        yield (rng[0][cur]-xmin, rng[1][cur])

class CollapseAlg:
    u"base class for collapse. Deals with stitching as well"
    def __init__(self, **kwa):
        self.edge   = kwa.get('edge', 1) # type: Optional[int]

    @property
    def _edge(self):
        return None if self.edge is None or self.edge < 1 else int(self.edge)

    def __call__(self, inter:Iterable) -> Profile:
        if hasattr(inter, '__next__'):
            inter  = tuple(inter)
        return self._run(cast(Sequence, inter), Profile(inter))

    def _run(self, inter:Sequence, prof:Profile) -> Profile:
        raise NotImplementedError()

    @classmethod
    def run(cls, inter:Iterable, **kwa) -> Profile:
        u"creates the configuration and runs the algorithm"
        return cls(**kwa)(inter)

class CollapseToMean(CollapseAlg):
    u"Collapses intervals together using their mean values"
    def _run(self, inter:Sequence, prof:Profile) -> Profile:
        key   = lambda i: (-i[0][-1], len(i[0]))

        cnt   = np.zeros_like(prof.count)
        vals  = prof.value
        edge  = self._edge
        inner = slice(edge, None if edge is None else -edge)
        for inds, cur in _iter_ranges(prof.xmin, sorted(inter, key = key)):
            if all(cnt[inds] == 0):
                vals[inds] -= cur.mean()
            else:
                vals[inds] += np.average(vals[inds], weights = cnt[inds]) - cur.mean()

            cnt [inds]              += 1
            prof.value[inds]        += cur
            prof.count[inds[inner]] += 1

        inds        = cnt > 0
        vals[inds] /= cnt[inds]
        return prof

class DerivateMode(Enum):
    u"Computation modes for the derivate method."
    median = 'median'
    mean   = 'mean'

class CollapseByDerivate(CollapseAlg):
    u"""
    Behaviour common to all is measured using the distribution of derivates at
    each time frame. Either the mean or the median is defined as the profile
    derivate.
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.maxder = kwa.get('maxder', np.inf)
        self.mode   = kwa.get('mode',   'median') # type: Union[str,DerivateMode]

    @staticmethod
    def __indexes(rng, xmin:Optional[int] = None, xmax:Optional[int] = None) -> np.ndarray:
        u'returns indexes linked to this range'
        if xmax is None:
            return rng[rng >= xmin] - xmin
        elif xmin is None:
            return rng[rng < xmax]
        else:
            return rng[np.logical_and(rng >= xmin, rng < xmax)] - xmin

    @classmethod
    def __occupation(cls, inter, xmin:int, xmax:int) -> np.ndarray:
        u"returns the number of overlapping intervals in the [xmin, xmax] range"
        ret = np.zeros((xmax-xmin,), dtype = np.int32)
        for rng in inter:
            ret[cls.__indexes(rng[0], xmin, xmax)] += 1
        return ret

    def _run(self, inter:Sequence, prof:Profile) -> Profile:
        vals  = np.full((prof.count.shape[0], max(self.__occupation(inter, prof.xmin, prof.xmax))),
                        np.inf, dtype = np.float32)
        cnt   = np.zeros_like(prof.count)
        occ   = prof.count
        inner = slice(self._edge, None)

        # compactify all derivatives into a single 2D table
        # missing values are coded as NaN
        for inds, cur in _iter_ranges(prof.xmin, inter):
            sel  = np.where(np.diff(inds) == 1)
            inds = inds[sel]

            vals[inds, max(cnt[inds])] = tuple(cur[i]-cur[i+1] for i in sel)
            cnt[inds]                 += 1
            occ[inds[inner]]          += 1

        vals[vals >= self.maxder] = np.NaN
        vals[:,0][cnt == 0]       = 0 # suppress all NaN warning

        fcn        = getattr(np, 'nan'+DerivateMode(self.mode).value)
        prof.value = pandas.Series(fcn(vals, axis = 1)[::-1]).cumsum().values[::-1]
        return prof

def _getintervals(cnt:np.ndarray, minv:int, neq:Callable) -> numpy.ndarray:
    u"returns a 2D array containing ranges with prof.count < minv"
    holes  = np.zeros((len(cnt)+2,), dtype = 'bool')
    neq(cnt, minv, out = holes[1:len(cnt)+1])
    inters = np.nonzero(np.diff(holes))[0]
    return inters.reshape((len(inters)//2,2))

class StitchByDerivate(CollapseByDerivate):
    u"""
    Fills holes using CollapseByDerivate as a method
    CollapseByDerivate for filling holes.
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.minoverlaps = kwa.get('minoverlaps', 10)

    # pylint: disable=arguments-differ
    def __call__(self, data: Iterable, prof: Profile) -> Profile: # type: ignore
        if hasattr(data, '__next__'):
            data  = tuple(data)

        der   = super().__call__
        last  = None # type: Optional[int]
        tmp   = None # type: Optional[Profile]
        for start, stop in _getintervals(prof.count, self.minoverlaps, np.less):
            if tmp is not None:
                prof.value[last:start] += tmp.value[-1]-prof.value[last]

            sli        = slice(max(start-1, 0), stop+1)
            tmp        = der(((i[sli], j[sli]) for i, j in data))
            tmp.value += prof.value[sli.start]-tmp.value[0]

            ind        = 0 if start == 0 else 1
            prof.value[start:stop] = tmp.value[ind:ind+stop-start]
            prof.count[start:stop] = tmp.count[ind:ind+stop-start]

            last  = stop

        if tmp is not None and last < len(prof):
            prof.value[last:] += tmp.value[-1]-prof.value[last]
        return prof

    @classmethod
    def run(cls, data:Iterable, prof:Profile, **kwa) -> Profile: # type: ignore
        u"creates the configuration and runs the algorithm"
        return cls(**kwa)(data, prof)

class StitchByInterpolation:
    u"""
    Ensures the continuity of a profile using bilinear interpolation
    """
    def __init__(self, **kwa):
        self.fitlength   = kwa.get('fitlength',   10)
        self.fitorder    = kwa.get('fitorder',     1)
        self.minoverlaps = kwa.get('minoverlaps', 10)

    def __fit(self, rng, side, vals):
        if side:
            imin, imax = rng[0], min(rng[0]+self.fitlength, rng[1])
            xvals      = range(0, imax-imin)
        else:
            imin, imax = max(rng[0], rng[1]-self.fitlength), rng[1]
            xvals      = range(imin-imax+1, 1)
        return np.polyfit(xvals, vals[imin:imax], self.fitorder)

    def __call__(self, prof) -> Profile:
        # get intervals with enough overlaps and enough points to do a fit
        filled    = _getintervals(prof.count, self.minoverlaps, np.greater_equal)
        filled    = filled[np.dot(filled, [-1, 1]) >= (self.fitorder+1)]

        # now fit a polynomial to each end of these intervals
        leftpars  = np.apply_along_axis(self.__fit, 1, filled, False, prof.value)
        rightpars = np.apply_along_axis(self.__fit, 1, filled, True,  prof.value)

        # remove ends: no extrapolation
        holes = filled.ravel()[1:-1].reshape((len(filled)-1,2))

        last   = None # Optional[int]
        delta  = 0.
        for left, right, (start, stop) in zip(leftpars[:-1], rightpars[1:], holes):
            if last is not None:
                prof.value[last:start] += delta

            params              = np.zeros((max(3, self.fitorder+1),), dtype = 'f4')
            params[-len(left):] = left

            params[-1]  += delta
            coeff        = np.polyval(np.polyder(right, 1), 0)
            coeff       -= np.polyval(np.polyder(left,  1), stop-start+1)
            coeff       /= 2.*(stop-start+1)
            params[-3]  += coeff

            vals       = tuple(np.polyval(params, i) for i in range(1, stop-start+2))
            prof.value[start:stop] = vals[:-1]

            delta, last = vals[-1]-np.polyval(right, 0), stop

        if last is not None:
            prof.value[last:filled[-1,-1]] += delta

        if filled[0][0] != 0:           # extrapolate around 0
            prof.value[:filled[0][0]]   = prof.value[filled[0][0]]

        if filled[-1][-1] < len(prof):  # extrapolate around the end
            prof.value[filled[-1][-1]:] = prof.value[filled[-1][-1]-1]
        return prof

    @classmethod
    def run(cls, prof:Profile, **kwa) -> Profile:
        u"creates the configuration and runs the algorithm"
        return cls(**kwa)(prof)
