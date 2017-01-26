#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Interval detection: finding flat sections in the signal"

from    typing import (NamedTuple, Optional, # pylint: disable=unused-import
                       Iterator, Iterable, Sequence, Union, Callable, cast)
import  numpy as np

from  .                     import nanhfsigma
# pylint: disable=no-name-in-module,import-error
from  ._core.samples.normal import knownsigma as norm

class PrecisionAlg:
    u"Implements precision extraction from data"
    DATATYPE = Optional[Union[Sequence[np.ndarray],np.ndarray]]
    def __init__(self, **kwa):
        self.precision = kwa.get('precision', None) # type: Optional[float]

    def getprecision(self,
                     precision:Optional[float] = None,
                     data     :DATATYPE        = tuple()) -> float:
        u"""
        Returns the precision, possibly extracted from the data.
        Raises AttributeError if the precision was neither set nor could be
        extracted
        """
        if precision is None:
            precision = self.precision

        if precision > 0.:
            return float(precision)
        elif isinstance(data, (float, int)):
            return float(data)
        elif isinstance(data, Sequence[np.ndarray]):
            return nanhfsigma(data)
        elif isinstance(data, np.ndarray):
            if len(data) == 1:
                return nanhfsigma(data[0])
            return np.median(tuple(nanhfsigma(i) for i in data))

        raise AttributeError('Could not extract precision: no data or set value')

class SplitDetector(PrecisionAlg):
    u"""
    Detects flat stretches of value

    Flatness is defined pointwise: 2 points are flat if close enough one to the
    other. This closeness is defined using a p-value for 2 points belonging to
    the same normal distribution with a known sigma.

    The sigma (precision) is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.confidence = kwa.get('confidence',  0.1)
        self._window    = 1
        self._kern      = np.ones((2,))
        self._lrng      = np.arange(1)
        self._hrng      = np.arange(1)
        self._setwindow(kwa.get('window', 1))

    def _setwindow(self, window):
        self._window = max(window, 1)
        self._kern   = np.ones((self._window*2,))
        self._kern[-self._window:] = -1.
        self._lrng   = np.arange(self._window+1)[-1:0:-1]
        self._hrng   = np.arange(self._window)[1:]

    window = property(lambda self: self._window, _setwindow)

    def __call__(self,
                 data     : np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        if len(data) <= 1:
            return np.empty((0,2), dtype = 'i4')

        precision = self.getprecision(precision, data)
        window    = self._window
        thr       = norm.threshold(True, self.confidence, precision, window, window)

        nans      = np.isnan(data)
        if any(nans):
            data = data[~nans]

        delta           = np.convolve(data, self._kern, mode = 'same')
        delta[:window] -= self._lrng * data[0]
        if window > 1:
            delta[1-window:] += self._hrng * data[-1]

        ends = (np.abs(delta) >= (thr*window)).nonzero()[0]

        if len(ends) == 0:
            return np.array(((0,len(nans)),), dtype = 'i4')

        if len(data) < len(nans):
            # increase indexes back to former data
            ends += nans.cumsum()[~nans][ends]

        ends = np.repeat(ends, 2)
        ends = np.insert(ends, [0, len(ends)], [0, len(nans)])
        ends = ends.reshape((len(ends)//2, 2))
        return ends[np.nonzero(np.diff(ends, 1).ravel() > 1)[0]]

    @classmethod
    def run(cls, data, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(data)

class EventMerger(PrecisionAlg):
    u"""
    Merges neighbouring stretches of data.

    Two intervals are merged whenever the mean for the second cannot be
    certified as being below that of the first. The p-value is estimated
    considering that distributions for both stretches are normal with a know
    sigma.

    The sigma (precision) is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.confidence = kwa.get('confidence',  0.1)
        self.isequal    = kwa.get('isequal',     True)

    def __call__(self,
                 data     : np.ndarray,
                 intervals: np.ndarray,
                 precision: Optional[float] = None
                ) -> np.ndarray:
        if len(data) == 0 or len(intervals) == 0:
            return np.empty((0,2), dtype = 'i4')

        thr     = norm.threshold(self.isequal, self.confidence,
                                 self.getprecision(precision, data))

        cnts    = np.isnan(data)
        sums    = np.insert(np.where(cnts, 0., data).cumsum(), 0, 0)
        cnts    = np.insert((~cnts).cumsum(), 0, 0)

        def _stats(ix0, ix1):
            cnt  = cnts[ix1] - cnts[ix0]
            mean = (1e5 if cnt == 0 else (sums[ix1]-sums[ix0])/cnt)
            return (cnt, mean, 0.)

        def _test(rngs, i):
            prob = norm.value(self.isequal, _stats(*rngs[i]), _stats(*rngs[i+1]))
            return prob < thr

        while len(intervals) > 1:
            # merge == True: interval needs to be merged with next one
            merge       = np.zeros(len(intervals)+1, dtype = 'bool')
            merge[1:-1] = tuple(_test(intervals, i) for i in range(len(merge)-2))

            if not any(merge[1:-1]):
                break

            # inds: range of intervals to be merged
            inds                   = np.nonzero(np.diff(merge))[0]
            intervals[inds[::2],1] = intervals[inds[1::2],1]
            intervals              = intervals[np.nonzero(~merge[:-1])[0]]

        return intervals

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

class EventSelector:
    u"""
    Filters flat stretches:

    * clips the edges
    * makes sure their length is enough
    """
    def __init__(self, **kwa):
        self.edgelength = kwa.get('edgelength', 0)
        self.minlength  = kwa.get('minlength',  5)

    def __call__(self, intervals: np.ndarray) -> np.ndarray:
        edx  = self.edgelength
        minl = 2*edx+self.minlength
        if minl <= 0:
            return intervals
        else:
            intervals = intervals[np.nonzero(np.diff(intervals, 1) >= minl)[0]] # type: ignore
            if edx != 0:
                intervals[:,0] += edx
                intervals[:,1] -= edx
            return intervals

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

class EventDetector(PrecisionAlg):
    u"detects, mergers and selects intervals"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.split  = kwa.get('split',  None) or SplitDetector(**kwa)
        self.merge  = kwa.get('merge',  None) or EventMerger  (**kwa)
        self.select = kwa.get('select', None) or EventSelector(**kwa)

    def __call__(self, data:np.ndarray, precision: Optional[float] = None):
        precision = self.getprecision(precision, data)
        yield from self.select(self.merge(data, self.split(data, precision), precision))

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

IdRange = NamedTuple('IdRange', (('start', int), ('stop', int), ('cycle', int)))
def tocycles(starts, inters):
    u"""
    Assigns a cycle id to intervals. If the interval is over multiple cycles,
    one of those with the maximum number of points is chosen.

    Parameters:

    * *starts*: array of starting indexes for each cycle or track from which
    to extract that information.
    """
    if hasattr(starts, 'phaseid'):
        starts = starts.phaseid(all, 0)

    for cur in inters:
        cstart = np.searchsorted(starts,            cur.start, 'right')
        cstop  = np.searchsorted(starts[cstart-1:], cur.stop,  'right')+cstart-1

        if cstop == cstart:
            cyc = cstart
        elif cstop == cstart+1:
            cyc = cstart + (starts[cstart]-cur.start < cur.stop - starts[cstart])
        else:
            cnt    = np.diff(starts[cstart-1:cstop])
            cnt[0] = starts[cstart]-cur.start
            imax   = np.argmax(cnt)
            cyc    = cstop if cur.stop-starts[cstop-1] > cnt[imax] else cstart+imax

        yield IdRange(cur.start, cur.stop, cyc-1)

PIdRange = NamedTuple('IdRange', (('start', int), ('stop', int),
                                  ('cycle', int), ('phase', int)))
def tophaseandcycles(starts, inters):
    u"""
    Assigns a cycle and phase id to intervals. If the interval is over multiple
    cycles or phases, one of those with the maximum number of points is chosen.

    Parameters:

    * *starts*: 2D array of starting indexes for each cycle and phase, or track
    from which to extract that information.
    """
    if hasattr(starts, 'phaseid'):
        starts = starts.phaseid(all, all)

    nphases = starts.shape[1]
    yield from (PIdRange(start, stop, cycle//nphases, cycle % nphases)
                for start, stop, cycle in tocycles(starts.ravel(), inters))
