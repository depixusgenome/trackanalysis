#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interval extension: splitting may produce smaller intervals then necessary.

Their boundary is extended.
"""
from    abc     import ABC, abstractmethod

import  numpy   as     np
from    utils   import initdefaults

class IntervalExtension(ABC):
    """
    Extends intervals beyond the computed range up to a limit given by *window*.

    This means to remove the range size bias created by using a window to compute
    derivatives.
    """
    window = 3
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

    @classmethod
    def extend(cls, ends, data, precision, window):
        "extends the provided ranges by as much as *window*"
        if window <= 1 or len(ends) < 1:
            return ends

        newmin = cls.__apply(ends, data, precision, -window)
        newmax = cls.__apply(ends, data, precision,  window)

        over   = np.nonzero(newmax[:-1] > newmin[1:])[0]
        if len(over) != 0:
            newmax[over]   = (newmin[over+1]+newmax[over])//2
            newmin[over+1] = newmax[over]

        ends[:,0] = newmin
        ends[:,1] = newmax
        return ends

    def __call__(self, ends, data, precision):
        return self.extend(ends, data, precision, self.window)

    @staticmethod
    def _sidedata(inters, data, window, default, imax = None):
        side   = 1 if window > 0 else 0
        inters = np.repeat(inters, 2)
        out    = inters[side::2]
        out   += window
        if   window < 0:
            np.maximum(0         if imax is None else imax, out, out = out)
        else:
            np.minimum(len(data) if imax is None else imax, out, out = out)

        rngs = np.split(data, inters)[1::2]
        diff = abs(window)-np.diff(inters)[::2]
        inds = np.nonzero(diff)[0][::-1]
        for i, j in zip(inds, diff[inds]):
            rngs.insert(i+side, [default]*j)
        return np.concatenate(rngs).reshape((len(inters)//2, abs(window))).T

    @classmethod
    def __apply(cls, ends, data, precision, window):
        side = 1 if window > 0 else 0
        inds = ends[:,side], ends[:,1-side]

        test = cls._test(inds, data, precision, window)
        good = np.ones((test.shape[0], 1), dtype = 'bool')
        test = np.hstack([good, test] if side else [test, good])

        if side:
            fcn = lambda i: np.max(np.nonzero(i)[0])
        else:
            fcn = lambda i: np.min(np.nonzero(i)[0])+1-len(i)
        res = inds[0]+np.apply_along_axis(fcn, 1, test)

        if side:
            res[:-1] = np.minimum(res[:-1], inds[1][1:])  # no merging intervals!
        else:
            res[1:]  = np.maximum(res[1:],  inds[1][:-1]) # no merging intervals!
        return res

    @classmethod
    @abstractmethod
    def _test(cls, inds, data, precision, window):
        pass

class IntervalExtensionAroundMean(IntervalExtension):
    """
    Extends intervals beyond the computed range up to a limit given by *window*.
    The range is extended:

        1. by at most *window* points in any direction.
        2. up to and including the farthest point within *mean ± precision*
        where the mean is the average of the *window* points at the interval edge.

        For a window of 3, where upper triangles are the current selection, the
        range is extended to the left by 2 (up to ☺)

            ^
            |   X
            |              △
            |
            |     ⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯
            |                 △
            |     ☺
            |     ⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯⋯
            |
            |           △
            |
            |       X
            +----------------------->
    This means to remove the range size bias created by using a window to compute
    derivatives.
    """
    @classmethod
    def _test(cls, inds, data, precision, window):
        vals = cls._sidedata(inds[0], data, window, 1e30)
        meds = np.nanmean(cls._sidedata(inds[0], data, -window, np.NaN, inds[1]), 0)

        np.abs(np.subtract(vals, meds, out = vals), out = vals)
        vals[np.isnan(vals)] = 0.
        return (vals < precision).T

class IntervalExtensionAroundRange(IntervalExtension):
    """
    Extends intervals beyond the computed range up to a limit given by *window*.
    The range is extended:

        1. by at most *window* points in any direction.
        2. up to and including the farthest point within *mean ± precision*
        where the mean is the average of the *window* points at the interval edge.
        2. up to and including the farthest point within in the same range of values
        as the *window* points at the interval edge:

        For a window of 3, where upper triangles are the current selection, the
        range is extended to the left by 2 (up to ☺)

            ^
            |   X
            |     ⋯⋯⋯⋯⋯⋯⋯⋯ △
            |
            |
            |                   △
            |     ☺
            |
            |     ⋯⋯⋯⋯⋯ △
            |
            |       X
            +----------------------->



    This means to remove the range size bias created by using a window to compute
    derivatives.
    """
    @classmethod
    def _test(cls, inds, data, precision, window):
        vals  = cls._sidedata(inds[0], data, window, 1e30)

        refs  = cls._sidedata(inds[0], data, -window, np.NaN, inds[1])
        refs[0, np.all(np.isnan(refs), 0)] = np.finfo('f4').max

        meanv = np.nanmean(refs, 0)
        maxv  = np.maximum(np.nanmax(refs, 0), meanv+precision)
        minv  = np.minimum(np.nanmin(refs, 0), meanv-precision)
        vals[np.isnan(vals)] = 0.
        return np.logical_and(vals <= maxv, vals >= minv).T
