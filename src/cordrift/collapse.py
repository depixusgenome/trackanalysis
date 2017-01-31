#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Collapse intervals. The idea is to measure the behaviour common to all
stretches of data. This should be removed as it's source is either a (thermal,
electric, ...) drift or a mechanical vibration.
"""
from    typing          import (Optional, Union, Sized, # pylint: disable=unused-import
                                Callable, NamedTuple, Sequence, cast, Iterable,
                                Any, Tuple)
from    enum            import Enum
import  pandas
import  numpy as np
from    signalfilter    import Filter, NonLinearFilter  # pylint: disable=unused-import

Range = NamedTuple('Range', [('start', int), ('values', np.ndarray)])

class Profile(Sized):
    u"A bead profile: the behaviour common to all stretches of data"
    def __init__(self, inter:Union[Sequence[Range],int]) -> None:
        if isinstance(inter, int):
            self.xmin  = 0      # type: int
            self.xmax  = inter  # type: int
        else:
            self.xmin  = min(i.start               for i in inter)
            self.xmax  = max(i.start+len(i.values) for i in inter)

        length     = self.xmax-self.xmin
        self.count = np.zeros((length,), dtype = np.int32)
        self.value = np.zeros((length,), dtype = np.float32)

    def __len__(self):
        return len(self.count)

def _iter_ranges(xmin:int, inter:Sequence[Range]) -> 'Iterable[Tuple[np.ndarray, np.ndarray]]':
    for rng in inter:
        if len(rng.values) == 0 or rng.start+len(rng.values) <= xmin:
            continue

        vals = rng.values[max(xmin-rng.start, 0):]
        good = np.isfinite(vals)
        if any(good):
            good = np.nonzero(good)[0]
            yield (good+max(rng.start-xmin, 0), vals[good])

class _CollapseAlg:
    u"base class for collapse. Deals with stitching as well"
    def __init__(self, **kwa):
        self.edge   = kwa.get('edge', 0)                   # type: Optional[int]
        self.filter = kwa.get('filter', NonLinearFilter()) # type: Optional[Filter]

    @property
    def _edge(self):
        return None if self.edge is None or self.edge < 1 else int(self.edge)

    def __call__(self, inter:Iterable[Range]) -> Profile:
        if hasattr(inter, '__next__'):
            inter  = tuple(inter)
        inter = cast(Sequence[Range], inter)
        return self._run(inter, Profile(inter))

    def _run(self, inter:Sequence[Range], prof:Profile) -> Profile:
        raise NotImplementedError()

    @classmethod
    def run(cls, inter:Iterable[Range], **kwa) -> Profile:
        u"creates the configuration and runs the algorithm"
        return cls(**kwa)(inter)

class CollapseToMean(_CollapseAlg):
    u"""
    Collapses intervals together using their mean values.

    The collapse starts from the right-most interval and moves left.
    """
    def _run(self, inter:Sequence[Range], prof:Profile) -> Profile:
        key   = lambda i: (-i.start-len(i.values), len(i.values))

        cnt    = np.zeros_like(prof.count)
        edge   = self._edge
        inner  = slice(edge, None if edge is None else -edge)
        for inds, cur in _iter_ranges(prof.xmin, sorted(inter, key = key)):
            vals  = prof.value[inds]
            rho   = 1.*cnt[inds]

            delta = cur.mean()
            if any(rho):
                delta -= np.average(vals, weights = rho)

            np.subtract(cur, delta, out = cur)

            rho                     /= rho+1
            prof.value[inds]         = rho * (vals-cur) + cur
            cnt       [inds]        += 1
            prof.count[inds[inner]] += 1

        if self.filter is not None:
            self.filter(prof.value)
        return prof

class CollapseByMerging(_CollapseAlg):
    u"""
    Collapses intervals together using their mean values

    The collapse is done by merging intervals sharing the maximum number of points.
    """
    @staticmethod
    def __init_inters(inter):
        inters = []
        for start, vals in inter:
            fin = np.isfinite(vals)
            inters.append((start,
                           np.where(fin, vals, 0.) - np.nanmean(vals),
                           np.int32(fin))) # type: ignore
        return inters

    @staticmethod
    def __compute_commons(common, rngs, i):
        cur  = common[:,i]
        rng  = rngs[i]

        np.minimum (rngs[:,1], rng[1],                        out = cur)
        np.subtract(cur,       np.maximum(rngs[:,0], rng[0]), out = cur)
        np.maximum (cur,       0,                             out = cur)
        cur[i] = 0

    @classmethod
    def __init_common(cls, inters):
        rngs   = np.array([[start, start+len(vals)] for start, vals, _ in inters])
        common = np.zeros((len(rngs), len(rngs)), dtype = 'i4')
        for i in range(len(rngs)):
            cls.__compute_commons(common, rngs, i)
        return rngs, common

    @staticmethod
    def __merge(rng1, rng2):
        start = min(rng1[0], rng2[0])
        stop  = max(rng1[0]+len(rng1[1]), rng2[0]+len(rng2[1]))
        vals  = np.zeros((stop-start,), dtype = 'f4')
        cnt   = np.zeros((stop-start,), dtype = 'i4')

        cnt[rng1[0]-start:][:len(rng1[2])]  = rng1[2]
        cnt[rng2[0]-start:][:len(rng2[2])] += rng2[2]

        vals[rng1[0]-start:][:len(rng1[1])]  = rng1[1] * rng1[2]
        vals[rng2[0]-start:][:len(rng2[1])] += rng2[1] * rng2[2]
        vals[cnt > 0] /= cnt[cnt > 0]
        return start, vals, cnt

    def __update_prof(self, prof, inters, rngs):
        for i, rng in enumerate(rngs):
            if rng[0] == rng[1]:
                continue

            start, vals, cnt = inters[i]
            ix1  = max(start, prof.xmin)
            ix2  = min(start+len(vals), prof.xmax)
            prof.value[ix1-prof.xmin:ix2-prof.xmin] = vals[ix1-start:ix2-start]

            ix1 += self.edge or 0
            ix2 -= self.edge or 0
            if ix2 > ix1:
                prof.count[ix1-prof.xmin:ix2-prof.xmin] = cnt [ix1-start:ix2-start]

    def _run(self, inter:Sequence[Range], prof:Profile) -> Profile:
        inters       = self.__init_inters(inter)
        rngs, common = self.__init_common(inters)
        ncols        = common.shape[1]

        for _ in range(len(inters)-1):
            imax = np.argmax(common)
            ind  = imax // ncols, imax % ncols
            if common[ind[0],ind[1]] <= 0:
                break

            start, vals, cnt = self.__merge(inters[ind[0]], inters[ind[1]])

            inters[ind[0]] = start, vals, cnt
            rngs  [ind[0]] = start, start + len(vals)
            rngs  [ind[1]] = 0, 0

            self.__compute_commons(common, rngs, ind[0])
            common [ind[1],:] = 0
            common [:,ind[1]] = 0

        self.__update_prof(prof, inters, rngs)

        if self.filter is not None:
            self.filter(prof.value)
        return prof

class DerivateMode(Enum):
    u"Computation modes for the derivate method."
    median = 'median'
    mean   = 'mean'

class CollapseByDerivate(_CollapseAlg):
    u"""
    Behaviour common to all is measured using the distribution of derivates at
    each time frame. Either the mean or the median is defined as the profile
    derivate.
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.maxder = kwa.get('maxder', np.inf)   # type: float
        self.mode   = kwa.get('mode',   'median') # type: Union[str,DerivateMode]

    @classmethod
    def __occupation(cls, inter:Sequence[Range], xmin:int, xmax:int) -> np.ndarray:
        u"returns the number of overlapping intervals in the [xmin, xmax] range"
        ret = np.zeros((xmax-xmin,), dtype = np.int32)
        for rng in inter:
            ret[max(rng.start-xmin,0) : max(rng.start+len(rng.values)-xmin, 0)] += 1
        return ret

    def _run(self, inter:Sequence[Range], prof:Profile) -> Profile:
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

        fcn    = getattr(np, 'nan'+DerivateMode(self.mode).value)
        values = fcn(vals, axis = 1)
        if self.filter is not None:
            self.filter(values)
        prof.value = pandas.Series(values[::-1]).cumsum().values[::-1]
        return prof

def _getintervals(cnt:np.ndarray, minv:int, neq:Callable) -> np.ndarray:
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
    def __call__(self, prof: Profile, data: 'Iterable[Range]') -> Profile: # type: ignore
        if hasattr(data, '__next__'):
            data = tuple(data)
        data  = cast(Sequence[Range], data)

        der   = super().__call__
        last  = None # type: Optional[int]
        tmp   = None # type: Optional[Profile]
        for start, stop in _getintervals(prof.count, self.minoverlaps, np.less):
            if tmp is not None:
                prof.value[last:start] += tmp.value[-1]-prof.value[last]

            sli  = slice(max(start-1, 0), stop+1)
            mins = (max(sli.start, rng.start)                  for rng in data)
            lens = (max(sli.stop-max(sli.start, rng.start), 0) for rng in data)
            tmp  = der(Range(start, rng.values[start-rng.start:start-rng.start+stop])
                       for start, stop, rng in zip(mins, lens, data))

            ind  = 0 if start == 0 else 1

            # assert all(np.isfinite(tmp.value)) # DEBUG check
            tmp.value += prof.value[max(start-1, 0)] - tmp.value[0]

            prof.value[start:stop] = tmp.value[ind:ind+stop-start]
            prof.count[start:stop] = tmp.count[ind:ind+stop-start]

            last  = stop

        if tmp is not None and last < len(prof):
            prof.value[last:] += tmp.value[-1]-prof.value[last]
        return prof

    @classmethod
    def run(cls, prof:Profile, data:'Iterable[Range]', **kwa) -> Profile: # type: ignore
        u"creates the configuration and runs the algorithm"
        return cls(**kwa)(prof, data)

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

    def __ranges(self, prof, filled):
        # fit a polynomial to each end of these intervals
        leftpars  = np.apply_along_axis(self.__fit, 1, filled, False, prof.value)
        rightpars = np.apply_along_axis(self.__fit, 1, filled, True,  prof.value)

        # remove ends: no extrapolation
        holes = filled.ravel()[1:-1].reshape((len(filled)-1,2))
        return zip(leftpars[:-1], rightpars[1:], holes)

    def __interp(self, left, right, rng, delta):
        length = rng[1]-rng[0]+1
        coeff  = np.polyval(np.polyder(right, 1), 0)
        coeff -= np.polyval(np.polyder(left,  1), length)
        coeff /= 2.*length

        params              = np.zeros((max(3, self.fitorder+1),), dtype = 'f4')
        params[-len(left):] = left
        params[-1]         += delta
        params[-3]         += coeff

        return tuple(np.polyval(params, i) for i in range(1, length+1))

    def __call__(self, prof:Profile, *_) -> Profile:
        # get intervals with enough overlaps and enough points to do a fit
        filled = _getintervals(prof.count, self.minoverlaps, np.greater_equal)
        filled = filled[np.dot(filled, [-1, 1]) >= (self.fitorder+1)]

        last   = None # Optional[int]
        delta  = 0.
        for left, right, rng in self.__ranges(prof, filled):
            if last is not None:
                prof.value[last:rng[0]] += delta

            vals                    = self.__interp(left, right, rng, delta)
            prof.value[slice(*rng)] = vals[:-1]
            delta, last             = vals[-1]-np.polyval(right, 0), rng[1]

        if last is not None:
            prof.value[last:filled[-1,-1]] += delta

        if filled[0][0] != 0:           # extrapolate around 0
            prof.value[:filled[0][0]]   = prof.value[filled[0][0]]

        if filled[-1][-1] < len(prof):  # extrapolate around the end
            prof.value[filled[-1][-1]:] = prof.value[filled[-1][-1]-1]
        return prof

    @classmethod
    def run(cls, prof:Profile, *_, **kwa) -> Profile:
        u"creates the configuration and runs the algorithm"
        return cls(**kwa)(prof)

CollapseAlg = Union[CollapseByDerivate, CollapseToMean, CollapseByMerging]
StitchAlg   = Union[StitchByDerivate,   StitchByInterpolation]
