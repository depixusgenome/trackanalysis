#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tasks related to peakfinding"
from   typing   import  Optional # pylint: disable=unused-import
import numpy    as      np

from eventdetection.alignment   import CorrelationAlignment
from .histogram                 import Histogram, CWTPeakFinder, GroupByPeak

class FindPeaks:
    u"Groups events per peak"
    histogram = Histogram()
    align     = CorrelationAlignment() # type: Optional[CorrelationAlignment]
    find      = CWTPeakFinder()        # type: CWTPeakFinder
    group     = GroupByPeak()          # type: GroupByPeak
    def __init__(self, **kwa):
        super().__init__()
        get = lambda x: kwa.get(x, getattr(self.__class__, x))
        self.histogram = get('histogram')
        self.align     = get('align')
        self.find      = get('find')
        self.group     = get('group')

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
