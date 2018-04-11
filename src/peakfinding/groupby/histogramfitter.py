#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a histogram from available events"
from enum import Enum
from typing import (Callable, Iterable, Optional,
                    Sequence, Union, cast)

import numpy as np
from numpy.lib.stride_tricks import as_strided
from scipy.signal import find_peaks_cwt

from utils import initdefaults
from utils.logconfig import getLogger


LOGS       = getLogger(__name__)

class FitMode(Enum):
    "Fit mode for sub-pixel peak finding"
    quadratic = 'quadratic'
    gaussian  = 'gaussian'

class SubPixelPeakPosition:
    """
    Refines the peak position using a quadratic fit
    """
    fitwidth: Optional[int] = 1
    fitcount                = 2
    fitmode                 = FitMode.quadratic
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __setstate__(self, kwa):
        self.__init__(**kwa)

    def __call__(self,
                 hist :Sequence[float],
                 ainds:Union[int, Sequence[int]],
                 bias :float = 0.,
                 rho  :float = 1.):
        if self.fitwidth is None or self.fitwidth < 1:
            return ainds

        if self.fitmode is FitMode.quadratic:
            def _fitfcn(i, j, k):
                if i+2 < j:
                    fit = np.polyfit(range(i,j), hist[i:j], 2)
                    if fit[0] < 0.:
                        return -fit[1]/fit[0]*.5
                return k
            fitfcn = _fitfcn
        else:
            fitfcn = lambda i, j, _: np.average(range(i,j), weights = hist[i:j])

        inds = (ainds,) if np.isscalar(ainds) else ainds
        for _ in range(self.fitcount):
            rngs = ((max(0,         i-self.fitwidth),
                     min(len(hist), i+self.fitwidth+1),
                     i) for i in cast(Iterable, inds))

            vals = np.array([fitfcn(*i) for i in rngs], dtype = 'f4')
            inds = np.int32(np.rint(vals))      # type: ignore
        return (vals[0] if np.isscalar(ainds) else vals) * rho + bias

class CWTPeakFinder:
    "Finds peaks using scipy's find_peaks_cwt. See the latter's documentation"
    subpixel                               = SubPixelPeakPosition()
    widths:        Sequence[int]           = np.arange(5, 11)
    wavelet:       Optional[Callable]      = None
    max_distances: Optional[Sequence[int]] = None
    gap_tresh:     Optional[float]         = None
    min_length:    Optional[int]           = None
    min_snr                                = 1.
    noise_perc                             = 10.
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **_):
        pass

    def __call__(self, hist: np.ndarray, bias:float = 0., slope:float = 1.):
        vals = find_peaks_cwt(hist, self.widths, self.wavelet, self.max_distances,
                              self.gap_tresh, self.min_length, self.min_snr,
                              self.noise_perc)
        if self.subpixel:
            vals = self.subpixel(hist, vals)

        return np.asarray(vals) * slope + bias

class ZeroCrossingPeakFinder:
    """
    Finds peaks with a minimum *half*width and threshold
    """
    subpixel         = SubPixelPeakPosition()
    peakwidth        = 3
    threshold: float = getattr(np.finfo('f4'), 'resolution')
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **_):
        pass

    def __call__(self, hist: np.ndarray, bias:float = 0., slope:float = 1.):
        roll                 = np.pad(hist, self.peakwidth, 'edge')
        roll[np.isnan(roll)] = -np.inf

        roll = as_strided(roll,
                          shape    = (len(hist), 2*self.peakwidth+1),
                          strides  = (hist.strides[0],)*2)

        maxes = np.apply_along_axis(np.argmax, 1, roll) == self.peakwidth
        inds  = np.where(maxes)[0]
        inds  = inds[hist[inds] > self.threshold]

        if self.subpixel:
            inds = self.subpixel(hist, inds)
        return inds * slope + bias

class PeakFlagger: # old name GroupByPeak
    """
    Groups events by peak position.

    Attributes:

        * *mincount:* Peaks with fewer events are discarded.
        * *window:*   The maximum distance of an event to the peak position, in
        units of precision.
    """
    window       = 2.5
    mincount     = 3
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def _bins(self, peaks:np.ndarray, precision):
        window        = self.window*(1. if precision is None else precision)
        bins          = (np.repeat(peaks, 2).reshape((len(peaks), 2))
                         + [-window, window]).ravel()
        diff          = bins[1:-1].reshape((len(peaks)-1,2))
        div           = np.where(np.diff(diff, 1) < 0)[0]
        bins[2*div+1] = np.mean(diff[div], 1)
        bins          = np.delete(bins, 2*div+2)

        inds          = np.full((len(bins)+1,), len(peaks), dtype = 'i4')
        inds[np.searchsorted(bins, peaks)] = np.arange(len(peaks))
        return bins, inds

    @staticmethod
    def _counts(elems, bins, inds):
        tags = inds[np.digitize(np.concatenate(elems), bins)]
        cnts = np.bincount(tags)

        # inds[0] is for underflows: one of the ids to discard
        # if cnt has anything to discard, it has a size == ids[0]
        if len(cnts) == inds[0]+1:
            cnts[-1] = 0 # discard counts for events outside peak windows
        return tags, cnts

    @staticmethod
    def _grouped(elems, ids, bad):
        ids[np.in1d(ids, bad)] = np.iinfo('i4').max

        sizes  = np.insert(np.cumsum([len(i) for i in elems]), 0, 0)
        sizes  = as_strided(sizes,
                            shape   = (len(sizes)-1, 2),
                            strides = (sizes.strides[0],)*2)
        ret    = np.empty((len(sizes),), dtype = 'O')
        ret[:] = [ids[i:j] for i, j in sizes]
        return ret

    def __call__(self, peaks, elems, precision = None):
        bins, inds = self._bins(peaks, precision)
        tags, cnts = self._counts(elems, bins, inds)
        return self._grouped(elems, tags, np.where(cnts < self.mincount)[0])

class GroupByPeakAndBase(PeakFlagger):
    """
    Groups events by peak position, making sure the baseline peak is kept

    Attributes:

        * *baserange:* the range starting from the very left where the baseline
        peak should be, in µm.
    """
    baserange = .1
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def _counts(self, elems, bins, inds):
        tags, cnts = super()._counts(elems, bins, inds)
        if len(cnts) < inds[0]+1:
            cnts = np.append(cnts, -1)
        imax       = max(inds[1:np.searchsorted(bins, bins[0]+self.baserange)+1],
                         default = -1, key = cnts.__getitem__)
        if imax >= 0:
            imin       = min(i for i in range(imax+1) if cnts[i] == cnts[imax])
            cnts[imin] = self.mincount # make sure peak is accepted
        return tags, cnts

class ByHistogram:
    """
    Finds peaks with a minimum *half*width and threshold
    """
    finder           = ZeroCrossingPeakFinder()
    grouper          = GroupByPeakAndBase()
    @initdefaults(frozenset(locals()), subpixel = 'update')
    def __init__(self, **kwa):
        pass
    def __call__(self,**kwa):
        hist  = kwa.get("hist",(np.array([]),0,1))
        peaks = self.finder(*hist)
        ids   = self.grouper(peaks     = peaks,
                             elems     = kwa.get("pos"),
                             precision = kwa.get("precision",None))
        return peaks, ids
