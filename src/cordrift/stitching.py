#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stiches profiles together when some points are lacking.
"""
from    typing          import (Optional, Union, Callable, Sequence, Iterable,
                                Iterator, cast)

import  numpy as np
from    numpy.lib.stride_tricks import as_strided
from    scipy.optimize          import least_squares

from    utils           import initdefaults
from    .collapse       import Range, Profile, CollapseByDerivate

def _getintervals(cnt:np.ndarray, minv:int, neq:Callable) -> np.ndarray:
    "returns a 2D array containing ranges with prof.count < minv"
    holes  = np.zeros((len(cnt)+2,), dtype = 'bool')
    neq(cnt, minv, out = holes[1:len(cnt)+1])
    inters = np.nonzero(holes[1:] != holes[:-1])[0]
    return inters.reshape((len(inters)//2,2))

class StitchByDerivate(CollapseByDerivate):
    """
    Fills holes using CollapseByDerivate as a method
    CollapseByDerivate for filling holes.
    """
    minoverlaps = 10
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    # pylint: disable=arguments-differ,signature-differs
    def __call__(self, prof:Profile, data:Iterable[Range]) -> Profile: # type: ignore
        if hasattr(data, '__next__'):
            data = tuple(data)
        data  = cast(Sequence[Range], data)

        der                     = super().__call__
        last: Optional[int]     = None
        tmp:  Optional[Profile] = None
        for start, stop in _getintervals(prof.count, self.minoverlaps, np.less):
            if tmp is not None:
                prof.value[last:start] += tmp.value[-1]-prof.value[last]

            sli  = max(start-1, 0), stop+1
            mins = cast(Iterator[int], (max(sli[0], rng.start) for rng in data))
            lens = (max(sli[1]-max(sli[0], rng.start), 0) for rng in data)
            tmp  = der(Range(i, rng.values[i-rng.start:i-rng.start+j])
                       for i, j, rng in zip(mins, lens, data))

            ind  = 0 if start == 0 else 1

            tmp.value += prof.value[max(start-1, 0)] - tmp.value[0]

            prof.value[start:stop] = tmp.value[ind:ind+stop-start]
            prof.count[start:stop] = tmp.count[ind:ind+stop-start]

            last  = stop

        if tmp is not None and last is not None and last < len(prof):
            prof.value[last:] += tmp.value[-1]-prof.value[last]
        return prof

    @classmethod
    def run(cls, prof:Profile, data:'Iterable[Range]', **kwa) -> Profile: # type: ignore
        "creates the configuration and runs the algorithm"
        return cls(**kwa)(prof, data)

class StitchByInterpolation:
    """
    Ensures the continuity of a profile using bilinear interpolation
    """
    fitlength   = 10
    fitorder    =  1
    minoverlaps = 10
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

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
        if len(filled) == 0:
            prof.value[:] = 0
            prof.count[:] = 0
            return prof

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
        "creates the configuration and runs the algorithm"
        return cls(**kwa)(prof)

class SingleFitStitch:
    """
    Interpolates by computing a polynomial fitting values on both side of
    missing data combined with an additionnal parameter for removing the bias
    between both sides.
    """
    fitlength   = 10
    fitorder    =  2
    minoverlaps = 10
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def __fit(self, left, right, values):
        xvals  = np.concatenate([range(*left), range(*right)])
        xvals  = xvals[np.isfinite(values[xvals])]

        yvals  = values[xvals]
        ind    = left[1]-left[0] - np.isnan(values[left[0]:left[1]]).sum()
        xvals -= xvals[ind]

        def __compute(params):
            res        = yvals - np.polyval(params[1:], xvals)
            res[ind:] -= params[0]
            return res

        init   = np.polyfit(xvals[:ind], yvals[:ind], self.fitorder)
        delta  = np.nanmean(yvals[ind:] - np.polyval(init, xvals[ind:]))
        params = least_squares(__compute, x0 = np.insert(init, 0, delta)).x

        vals   = np.polyval(params[1:], range(left[1]-right[0], 1))
        return vals[:-1], params[0], right[0]

    def __call__(self, prof:Profile, *_) -> Profile:
        values = prof.value
        rngs   = _getintervals(prof.count, self.minoverlaps, np.greater_equal)
        if len(rngs) < 1:
            return prof
        if len(rngs) < 2:
            rngs = rngs[None]
        else:
            stride = rngs.strides[-1]*2, rngs.strides[-1]*2, rngs.strides[-1]
            rngs   = as_strided(rngs, shape = (len(rngs)-1,2,2), strides = stride)
            last   = None # Optional[int]
            delta  = 0.
            for left, right in rngs:
                if last is not None:
                    values[last:left[1]] -= delta

                left  = max(left[1]  -self.fitlength, left[0]), left[1]
                right = right[0], min(right[0]+self.fitlength, right[1])

                change, delta, last      = self.__fit(left, right, values)
                values[left[1]:right[0]] = change

            values[last:rngs[-1,-1,-1]] -= delta

        if rngs[0,0,0] != 0:           # extrapolate around 0
            values[:rngs[0,0,0]]   = values[rngs[0,0,0]]

        if rngs[-1,-1,-1] < len(values):  # extrapolate around the end
            values[rngs[-1,-1,-1]:] = values[rngs[-1,-1,-1]]
        return prof

    @classmethod
    def run(cls, prof:Profile, *_, **kwa) -> Profile:
        "creates the configuration and runs the algorithm"
        return cls(**kwa)(prof)

StitchAlg   = Union[StitchByDerivate, StitchByInterpolation, SingleFitStitch]
