#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to one another
"""
from    typing                      import Sequence, NamedTuple, Union
from    scipy.interpolate           import interp1d
from    scipy.optimize              import fmin_cobyla
import  numpy                       as     np

from    utils                       import initdefaults
from    peakfinding.histogram       import Histogram
from    peakfinding.probabilities   import Probability
from    ._base                      import (GriddedOptimization, CobylaParameters,
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

    histogram    = Histogram(precision = 0.001, edge = 4)
    symmetry     = True
    stretch      = Range(1., .05, .025)
    bias         = Range(0,   .1, .05)
    optim        = CobylaParameters((1e-2, 5e-3), (1e-4, 1e-4), None, None)
    minthreshold = 1e-3
    maxthreshold: Union[str, float, None] = 'auto'
    @initdefaults(frozenset(locals()),
                  precision = lambda self, i: setattr(self, 'precision', i))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    precision    = property(lambda self: self.histogram.precision,
                            lambda self, val: setattr(self.histogram, 'precision', val))
    def getprecision(self, *args, **kwargs):
        "returns the precision"
        return self.histogram.getprecision(*args, **kwargs)

    def frompeaks(self, peaks):
        "creates a histogram from a list of peaks with their count"
        if str(getattr(peaks, 'dtype', ' '))[0] != 'f':
            peaks = np.array([(i, Probability.resolution(j)) for i, j in peaks])
        return self.histogram.variablekernelsize(peaks)

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
            bias = np.asarray(bias)-right.minv+left.minv/np.asarray(stretch)
            ufcn = np.frompyfunc(lambda i, j: fcn(left, right, i, j), 2, 1)
            return ufcn(stretch, bias)
        return fcn(left, right, stretch, bias-right.minv+left.minv/stretch)

    def _get(self, left):
        left = self.histogram.asprojection(left)
        vals = (np.arange(len(left.histogram), dtype = 'f4')*left.binwidth,
                left.histogram)

        if self.minthreshold not in (None, np.NaN):
            mask = np.insert(left.histogram >= self.minthreshold,
                             [0, len(left.histogram)], True)
            np.logical_or(mask[:-2], mask[1:-1], mask[1:-1])
            mask = np.logical_or(mask[2:],  mask[1:-1], mask[1:-1])
            vals = vals[0][mask], vals[1][mask]

        if self.maxthreshold not in (None, np.NaN):
            thr = self.maxthreshold
            if thr == 'auto':
                pks = vals[1][1:-1][np.logical_and(vals[1][2:]  < vals[1][1:-1],
                                                   vals[1][:-2] < vals[1][1:-1])]
                thr = np.nanmedian(pks)
            if thr not in (None, np.NaN):
                vals[1][vals[1] > thr] = thr

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
