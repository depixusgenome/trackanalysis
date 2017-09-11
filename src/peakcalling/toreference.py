#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to one another
"""
from    typing                  import Sequence, NamedTuple, Iterator
from    scipy.interpolate       import interp1d
from    scipy.optimize          import fmin_cobyla
import  numpy                   as     np

from    utils                   import EventsArray, initdefaults
from    peakfinding.histogram   import HistogramData, Histogram
from    ._base                  import (GriddedOptimization, CobylaParameters,
                                        Distance, Range, DEFAULT_BEST)

class ReferenceDistance(GriddedOptimization):
    """
    Matching experimental peaks by correlating peak positions in the histograms
    """
    class Data(NamedTuple): # pylint: disable=missing-docstring
        fcn:   interp1d
        xaxis: np.ndarray
        yaxis: np.ndarray
        minv:  float

    histogram    = Histogram(precision = 0.001)
    symmetry     = True
    stretch      = Range(1., .05, .025)
    bias         = Range(0,   .1, .05)
    optim        = CobylaParameters((1e-2, 5e-3), (1e-4, 1e-4), None, None)
    minthreshold = 1e-3
    maxthreshold = .5
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def optimize(self, aleft, aright):
        "find best stretch & bias to fit right against left"
        left  = self._get(aleft)
        right = self._get(aright)
        fcn   = self._sym if self.symmetry else self._asym
        cost  = lambda x: fcn(left, right, *x)
        kwa   = self.optimconfig(disp = 0, cons = self.__constraints())

        def _go():
            for i in self.grid:
                tmp = fmin_cobyla(cost, i, **kwa)
                yield (cost(tmp), tmp[0], tmp[1])

        ret = min(_go(), default = (DEFAULT_BEST, 1., 0.))
        return Distance(ret[0], ret[1], ret[2]+right.minv-left.minv/ret[1])

    def value(self, aleft, aright, stretch, bias):
        "compute cost value for fitting right against left with given stretch & bias"
        left  = self._get(aleft)
        right = self._get(aright)
        fcn   = self._sym if self.symmetry else self._asym
        if any(isinstance(i, (np.ndarray, Sequence)) for i in  (stretch, bias)):
            print(bias.shape, left.minv, right.minv)
            bias = np.asarray(bias)-right.minv+left.minv/np.asarray(stretch)
            ufcn = np.frompyfunc(lambda i, j: fcn(left, right, i, j), 2, 1)
            return ufcn(stretch, bias)
        return fcn(left, right, stretch, bias-right.minv+left.minv/stretch)

    def _get(self, left):
        if hasattr(left, 'histogram'):
            pass
        elif ((isinstance(left, np.ndarray) and str(left.dtype)[0] == 'f') or
              (isinstance(left, Sequence) and all(np.isscalar(i) for i in left))):
            left = self.histogram.projection(left)
        elif isinstance(left, EventsArray):
            left = self.histogram.projection(left)
        elif isinstance(left, Iterator):
            # this should be a peaks output
            vals = np.concatenate([i for _, i in left])
            vals = np.concatenate([i if isinstance(i, np.ndarray) else [i]
                                   for i in vals if i is not None and len(i)])
            left = self.histogram.projection(vals)
        else:
            left = HistogramData(*left)

        vals = (np.arange(len(left.histogram), dtype = 'f4')*left.binwidth,
                left.histogram)

        if self.minthreshold is not None:
            mask = np.insert(left.histogram >= self.minthreshold,
                             [0, len(left.histogram)], True)
            np.logical_or(mask[:-2], mask[1:-1], mask[1:-1])
            mask = np.logical_or(mask[2:],  mask[1:-1], mask[1:-1])
            vals = vals[0][mask], vals[1][mask]

        if self.maxthreshold is not None:
            vals[1][vals[1] > self.maxthreshold] = self.maxthreshold

        fcn = interp1d(*vals,
                       fill_value    = 0.,
                       bounds_error  = False,
                       assume_sorted = True)
        return self.Data(fcn, *vals, left.minvalue)

    @classmethod
    def _sym(cls, left, right, stretch, bias):
        return (cls._asym(left, right, stretch, bias)
                + cls._asym(right, left, 1./stretch, -stretch*bias))

    @staticmethod
    def _asym(left, right, stretch, bias):
        return -(left.fcn((right.xaxis-bias)*stretch)*right.yaxis).sum()

    def __constraints(self):
        sleft  = self.stretch.center - self.stretch.size - .5*self.stretch.step
        sright = self.stretch.center + self.stretch.size + .5*self.stretch.step

        cntr   = 0. if self.bias.center is None else self.bias.center
        bleft  = cntr - self.bias.size - .5*self.bias.step
        bright = cntr + self.bias.size + .5*self.bias.step
        return [lambda x: x[0]-sleft, lambda x: sright-x[0],
                lambda x: x[1]-bleft, lambda x: bright-x[1]]
