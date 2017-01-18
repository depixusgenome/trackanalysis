#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Interval detection: finding flat sections in the signal"

from    typing import NamedTuple
import  numpy

# pylint: disable=no-name-in-module,import-error
from  ._core.samples.normal import knownsigma
from  ._core.stats          import hfsigma

class DetectFlats:
    u"""
    Detects flat stretches of value.

    Flatness is defined pointwise: 2 points are flat if close enough one to the
    other. This closeness is defined using a p-value for 2 points belonging to
    the same normal distribution with a known sigma.

    The sigma (precision) is either provided or measured. In the latter case,
    the estimation used is the median-deviation of the derivate of the data.
    """
    def __init__(self, **kwa):
        self.precision = kwa.get('precision', 0.)
        self.confidence  = kwa.get('confidence',  0.1)
        self._window     = 1
        self._kern       = numpy.ones((2,))
        self._lrng       = numpy.arange(1)
        self._hrng       = numpy.arange(1)
        self._setwindow(kwa.get('window', 1))

    def _setwindow(self, window):
        self._window = max(window, 1)
        self._kern   = numpy.ones((self._window*2,))
        self._kern[-self._window:] = -1.
        self._lrng   = numpy.arange(self._window+1)[-1:0:-1]
        self._hrng   = numpy.arange(self._window)[1:]

    window = property(lambda self: self._window, _setwindow)

    def __call__(self, data):
        if len(data) <= 1:
            return

        window    = self._window
        precision = hfsigma(data) if self.precision == 0 else self.precision
        thr       = knownsigma.threshold(True, self.confidence, precision,
                                         window, window)

        delta           = numpy.convolve(data, self._kern, mode = 'same')
        delta[:window] -= self._lrng * data[0]
        if window > 1:
            delta[1-window:] += self._hrng * data[-1]

        ends = (numpy.abs(delta) >= (thr*window)).nonzero()[0]

        if len(ends) == 0:
            yield slice(0, len(data))
        else:
            start = 0
            for end in ends:
                if start+1 < end:
                    yield slice(start, end)
                start = end
            if start+1 < len(data):
                yield slice(start, len(data))

    @classmethod
    def run(cls, data, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(data)

class MergeFlats:
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
        self.precision = kwa.get('precision', 0.)
        self.confidence  = kwa.get('confidence',  0.1)
        self.isequal     = kwa.get('isequal',     True)

    def __call__(self, data, intervals):
        if len(data) == 0:
            return

        iinter      = iter(intervals)
        last        = next(iinter, None)
        if last is None:
            return

        precision = hfsigma(data) if self.precision == 0 else self.precision
        thr       = knownsigma.threshold(self.isequal, self.confidence, precision)
        if self.isequal:
            check = lambda i, j: knownsigma.value(True,  i, j) < thr
        else:
            check = lambda i, j: knownsigma.value(False, i, j) > thr

        statslast = last.stop-last.start, data[last].mean(), 0.
        for cur in iinter:
            statscur = cur.stop - cur.start, data[cur].mean(), 0.
            if check(statscur, statslast):
                last      = slice(last.start, cur.stop)
                statslast = last.stop-last.start, data[last].mean(), 0.
            else:
                yield last
                last      = cur
                statslast = statscur
        yield last

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

class FilterFlats:
    u"""
    Filters flat stretches:

    * clips the edges
    * makes sure their length is enough
    """
    def __init__(self, **kwa):
        self.edgelength = kwa.get('edgelength', 0)
        self.minlength  = kwa.get('minlength',  5)

    def __call__(self, intervals):
        edx  = self.edgelength
        minl = 2*edx+self.minlength
        if minl <= 0:
            yield from intervals
        elif edx == 0:
            yield from (i for i in intervals if i.stop-i.start >= minl)
        else:
            yield from (slice(i.start+edx,i.stop-edx) for i in intervals
                        if i.stop-i.start >= minl)

    @classmethod
    def run(cls, *args, **kwa):
        u"instantiates and calls class"
        return cls(**kwa)(*args)

IdRange = NamedTuple('IdRange', (('start', int), ('stop', int), ('cycle', int)))
def tocycles(starts, inters):
    u"Takes intervals on a bead to intervals on cycles"
    if hasattr(starts, 'phaseid'):
        starts = starts.phaseid(all,0)

    for cur in inters:
        cyc  = numpy.searchsorted(starts, cur.start)
        bias = starts[max(0,cyc-1)]
        yield IdRange(cur.start-bias, cur.stop-bias, cyc)
