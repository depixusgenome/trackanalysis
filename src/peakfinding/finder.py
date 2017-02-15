#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from   typing   import  Optional # pylint: disable=unused-import
import numpy    as      np

from utils                    import initdefaults
from eventdetection.alignment import CorrelationAlignment
from .histogram               import (Histogram,  # pylint: disable=unused-import
                                      PeakFinder, ZeroCrossingPeakFinder, GroupByPeak)

class FindPeaks:
    u"Groups events per peak"
    histogram = Histogram()
    align     = CorrelationAlignment()
    find      = ZeroCrossingPeakFinder() # type: PeakFinder
    group     = GroupByPeak()
    @initdefaults('histogram', 'align', 'find', 'group')
    def __init__(self, **_):
        super().__init__()

    def __call__(self, data):
        events = np.array([[i for _, i in evts] for _, evts in data], dtype = 'O')
        pos    = self.histogram.eventpositions(events)

        if self.align is not None:
            hists, _, width = self.histogram(pos,
                                             edge      = 0,
                                             kernel    = None,
                                             zmeasure  = None,
                                             separate  = True)[0]
            delta   = self.align(hists, oversampling = 0)*width
            pos    += delta
            events  = events + delta

        hist, xmin, width = self.histogram(pos, zmeasure = None, separate = False)
        peaks             = self.find     (hist, xmin, width)
        ids               = self.group    (peaks, pos)
        for i in range(len(peaks)):
            if not any(i == j for j in ids):
                continue

            peakevents = np.array([evts[ind] for evts, ind in zip(events, ids)],
                                  dtype = 'O')
            yield peakevents
