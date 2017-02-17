#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Selects peaks and yields all events related to each peak"
from   typing   import  Optional # pylint: disable=unused-import
import numpy    as      np

from utils                    import initdefaults
from eventdetection.alignment import CorrelationAlignment
from .histogram               import (Histogram,  # pylint: disable=unused-import
                                      PeakFinder, ZeroCrossingPeakFinder, GroupByPeak)

class PeakSelector:
    u"Selects peaks and yields all events related to each peak"
    histogram = Histogram()
    align     = CorrelationAlignment()
    find      = ZeroCrossingPeakFinder() # type: PeakFinder
    group     = GroupByPeak()
    @initdefaults('histogram', 'align', 'find', 'group')
    def __init__(self, **_):
        pass

    def __call__(self, events, precision = None):
        precision = self.histogram.getprecision(precision, events)
        pos       = self.histogram.eventpositions(events)

        if self.align is not None:
            hists, _, width = self.histogram(pos,
                                             edge      = 0,
                                             kernel    = None,
                                             precision = precision,
                                             zmeasure  = None,
                                             separate  = True)
            delta   = self.align(hists, oversampling = 0)*width
            pos    += delta

        hist, xmin, width = self.histogram(pos,
                                           precision = precision,
                                           zmeasure  = None,
                                           separate  = False)

        peaks = self.find (hist, xmin, width)
        ids   = self.group(peaks, pos)
        for i, peak in enumerate(peaks):
            evts = np.array([evts[ind == i] for evts, ind in zip(events, ids)],
                            dtype = 'O')
            if any(len(i) for i in evts):
                yield (peak, evts+delta)
