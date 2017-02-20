#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Selects peaks and yields all events related to each peak"
from   typing   import  Iterable, Optional
from   copy     import  copy
import numpy    as      np

from utils      import initdefaults
from .alignment import PeakCorrelationAlignment
from .histogram import (Histogram, PeakFinder, # pylint: disable=unused-import
                        ZeroCrossingPeakFinder, GroupByPeak, asarray)

class PeakSelector:
    u"Selects peaks and yields all events related to each peak"
    histogram = Histogram(edge = 2)
    align     = PeakCorrelationAlignment()
    find      = ZeroCrossingPeakFinder() # type: PeakFinder
    group     = GroupByPeak()
    @initdefaults
    def __init__(self, **_):
        pass

    def __call__(self,
                 aevents  : Iterable[Iterable[np.ndarray]],
                 precision: Optional[float] = None):
        events    = asarray(aevents)
        projector = copy(self.histogram)
        projector.precision = projector.getprecision(precision, events)

        pos = projector.eventpositions(events)
        if self.align is not None:
            delta  = self.align(pos, projector = projector)
            pos   += delta
        else:
            delta  = 0.

        projector.zmeasure = None
        hist  = projector (pos, separate = False)

        peaks = self.find (next(hist[0]), *hist[1:])
        ids   = self.group(peaks, pos)
        for i, peak in enumerate(peaks):
            evts = np.array([np.concatenate(tuple(elems[ind == i]))
                             for elems, ind in zip(events, ids)],
                            dtype = 'O')
            if any(len(i) for i in evts):
                yield (peak, evts+delta)
