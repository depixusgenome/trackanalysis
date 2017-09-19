#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matching experimental peaks to one another
"""
from    typing                      import Sequence, NamedTuple, Tuple, Union, cast
from    functools                   import partial
from    scipy.interpolate           import interp1d
from    scipy.optimize              import fmin_cobyla
import  numpy                       as     np

from    utils                       import initdefaults
from    eventdetection.data         import Events
from    peakfinding.histogram       import Histogram, HistogramData
from    peakfinding.probabilities   import Probability
from    peakfinding.selector        import PeakSelectorDetails
from    ._base                      import (GriddedOptimization, CobylaParameters,
                                            Distance, Range, chisquare, chisquarevalue,
                                            DEFAULT_BEST)

class HistogramFitData(NamedTuple): # pylint: disable=missing-docstring
    fcn:   interp1d
    xaxis: np.ndarray
    yaxis: np.ndarray
    minv:  float

class ChiSquareData(NamedTuple): # pylint: disable=missing-docstring
    fcn:   interp1d
    xaxis: np.ndarray
    yaxis: np.ndarray
    minv:  float
    peaks: np.ndarray

FitData = Union[HistogramFitData, ChiSquareData]

class HistogramFit(GriddedOptimization):
    "Matching experimental peaks by correlating peak positions in the histograms"
    histogram    = Histogram(precision = 0.001, edge = 4)
    symmetry     = True
    stretch      = Range(1., .05, .02)
    bias         = Range(0,   .1, .01)
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

    def frompeaks(self, peaks, firstpeak = 0):
        "creates a histogram from a list of peaks with their count"
        if str(getattr(peaks, 'dtype', ' '))[0] != 'f':
            peaks = np.array([(i, Probability.resolution(j)) for i, j in peaks])
        peaks = peaks[firstpeak:,:]
        return self.histogram.variablekernelsize(peaks)

    def fromevents(self, evts:Events):
        "creates a histogram from a list of events"
        return self.histogram.asprojection(np.concatenate(list(evts.values())))

    def optimize(self, aleft, aright):
        "find best stretch & bias to fit right against left"
        np.seterr(under = "ignore")
        left  = self._get(aleft)
        right = self._get(aright)
        kwa   = self.optimconfig(disp = 0, cons = self.__constraints())
        ret   = min((self._optimize(left, right, kwa, i) for i in self.grid),
                    default = (DEFAULT_BEST, 1., 0.))

        return Distance(ret[0], ret[1], ret[2]+right.minv-left.minv/ret[1])

    def value(self, aleft, aright, stretch, bias):
        "compute cost value for fitting right against left with given stretch & bias"
        np.seterr(under = "ignore")
        left  = self._get(aleft)
        right = self._get(aright)
        fcn   = partial(self._cost_function, left, right)
        if any(isinstance(i, (np.ndarray, Sequence)) for i in  (stretch, bias)):
            bias = np.asarray(bias)-right.minv+left.minv/np.asarray(stretch)
            ufcn = np.frompyfunc(fcn, 2, 1)
            return ufcn(stretch, bias)
        return fcn(stretch, bias-right.minv+left.minv/stretch)

    def _get(self, left) -> FitData:
        hist, vals = self._to_2d(left)
        vals       = self._apply_minthreshold(vals)
        self._apply_maxthreshold(vals)
        return self._to_data(hist, vals)

    def _cost_function(self, left: FitData, right: FitData, stretch: float, bias: float):
        return (self._sym if self.symmetry else self._asym)(left, right, stretch, bias)

    def _optimize(self, left: FitData, right: FitData, kwa, params):
        if self.symmetry:
            cost = lambda x: self._sym(left, right, x[0], x[1])
        else:
            cost = lambda x: self._asym(left, right, x[0], x[1])
        tmp  = fmin_cobyla(cost, params, **kwa)
        return (cost(tmp), tmp[0], tmp[1])

    def _to_2d(self, left) -> Tuple[HistogramData, Tuple[np.ndarray, np.ndarray]]:
        left = self.histogram.asprojection(left)
        vals = (np.arange(len(left.histogram), dtype = 'f4')*left.binwidth,
                left.histogram)
        return left, vals

    def _apply_minthreshold(self, vals: Tuple[np.ndarray, np.ndarray]):
        if self.minthreshold not in (None, np.NaN):
            mask = np.insert(vals[1] >= self.minthreshold, [0, len(vals[1])], True)
            np.logical_or(mask[:-2], mask[1:-1], mask[1:-1])
            mask = np.logical_or(mask[2:],  mask[1:-1], mask[1:-1])
            vals = vals[0][mask], vals[1][mask]
        return vals

    def _apply_maxthreshold(self, vals: Tuple[np.ndarray, np.ndarray]):
        if self.maxthreshold not in (None, np.NaN):
            thr = self.maxthreshold
            if thr == 'auto':
                pks = vals[1][1:-1][np.logical_and(vals[1][2:]  < vals[1][1:-1],
                                                   vals[-1][:-2] < vals[1][1:-1])]
                thr = np.nanmedian(pks)
            if thr not in (None, np.NaN):
                vals[1][vals[1] > thr] = thr

    @classmethod
    def _to_data(cls,
                 left: HistogramData,
                 vals: Tuple[np.ndarray, np.ndarray]) -> FitData:
        fcn = interp1d(*vals,
                       fill_value    = 0.,
                       bounds_error  = False,
                       assume_sorted = True)
        return HistogramFitData(fcn, *vals, left.minvalue)

    @classmethod
    def _sym(cls, left: FitData, right : FitData, stretch: float, bias: float):
        return (cls._asym(left, right, stretch, bias)
                + cls._asym(right, left, 1./stretch, -stretch*bias))

    @staticmethod
    def _asym(left: FitData, right: FitData, stretch: float, bias: float):
        xvals = (right.xaxis-bias)*stretch
        fvals = left.fcn(xvals)
        res   = fvals*right.yaxis
        return -res.sum()

    def __constraints(self):
        sleft  = self.stretch.center - self.stretch.size - .5*self.stretch.step
        sright = self.stretch.center + self.stretch.size + .5*self.stretch.step

        cntr   = 0. if self.bias.center is None else self.bias.center
        bleft  = cntr - self.bias.size - .5*self.bias.step
        bright = cntr + self.bias.size + .5*self.bias.step
        return [lambda x: x[0]-sleft, lambda x: sright-x[0],
                lambda x: x[1]-bleft, lambda x: bright-x[1]]

class ChiSquareHistogramFit(HistogramFit):
    """
    Matching experimental peaks by:

    1. correlating peak positions in the histograms
    2. finding paired peaks
    3. fitting a linear regression to paired peaks
    """

    window    = 1.5e-2
    def frompeaks(self, peaks, firstpeak = 0):
        "creates a histogram from a list of peaks with their count"
        if str(getattr(peaks, 'dtype', ' '))[0] != 'f':
            peaks = np.array([(i, Probability.resolution(j)) for i, j in peaks])
        else:
            peaks = np.asarray(peaks)
        peaks = peaks[firstpeak:,:]
        return self.histogram.variablekernelsize(peaks), peaks[:,0]

    @staticmethod
    def _getpeaks(orig, data) -> np.ndarray:
        if isinstance(orig, PeakSelectorDetails):
            peaks = orig.peaks
        elif str(getattr(orig, 'dtype', ' '))[0] == 'f' and len(orig.shape) == 2:
            # expecting a 2D table as in hv.Curve.data
            peaks = orig[1:-1, 0][np.logical_and(orig[2:,  1] < orig[1:-1, 1],
                                                 orig[:-2, 1] < orig[1:-1, 1])]
        else:
            hist  = data[1]
            pos   = np.logical_and(hist[2:] < hist[1:-1], hist[:-2] < hist[1:-1])
            peaks = data[0][np.nonzero(pos)[0]]
        return cast(np.ndarray, np.unique(peaks))

    def _get(self, left) -> ChiSquareData:
        if isinstance(left, tuple):
            # returned from self.frompeaks
            left, peaks = left
        else:
            peaks       = None

        hist, vals  = self._to_2d(left)
        vals        = self._apply_minthreshold(vals)
        if peaks is None:
            peaks   = self._getpeaks(left, vals)

        self._apply_maxthreshold(vals)
        data        = self._to_data(hist, vals)
        return ChiSquareData(data.fcn, data.xaxis, data.yaxis, data.minv, peaks-data.minv)

    def _optimize(self, left: ChiSquareData, right: ChiSquareData,      # type: ignore
                  kwa, params):
        tmp = super()._optimize(left, right, kwa, params)
        res = chisquare(left.peaks, right.peaks,
                        False, self.symmetry, self.window, tmp[1], -tmp[1]*tmp[2])
        return res[0], res[1], -res[2]/res[1]

    def _cost_function(self, left: ChiSquareData, right: ChiSquareData, # type: ignore
                       stretch: float, bias: float):
        return chisquarevalue(left.peaks, right,
                              False, self.symmetry, self.window,
                              stretch, -stretch*bias)[0], stretch, bias
