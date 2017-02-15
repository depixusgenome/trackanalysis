#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests histogram  creation and analysis"
import numpy as np
from numpy.testing import assert_equal, assert_allclose

from peakfinding.histogram import (Histogram, CWTPeakFinder,
                                   ZeroCrossingPeakFinder, GroupByPeak)

def test_histogram():
    u"tests histogram creation"
    hist = Histogram(kernel = None, precision = 1)
    events = [[np.ones((5,)), np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5                  ]]

    out, xmin, delta = hist(events, separate = False)
    out              = tuple(out)
    assert xmin     == 1
    assert delta    == .2
    assert len(out) == 1
    assert len(out[0]) == 46

    truth     = np.zeros((46,), dtype = 'f4')
    truth[0]  = 1
    truth[-1] = 2
    truth[20] = 3
    assert_equal(truth, out[0])

    hist   = Histogram(precision = 1, edge = 8)
    events = [np.ones((5,))]
    out, xmin, delta = hist(events, separate = False)
    out              = tuple(out)[0]
    assert xmin     == -7
    assert delta    == .2
    assert len(out) == 81
    assert_allclose(out[40::-1], out[40:], rtol = 1e-5, atol = 1e-10)
    assert max(out) == out[40]

def test_peakfinder():
    u"tests peak finding"
    hist = Histogram(precision = 1, edge = 8)
    events = [[np.ones((5,)), np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5                  ]]

    out, xmin, bwidth = hist(events, separate = False)
    out   = next(out)
    truth = [1., 5., 10.]

    peaks = CWTPeakFinder()(out, xmin, bwidth)
    assert_allclose(peaks, truth, rtol = 1e-2)

    peaks = ZeroCrossingPeakFinder()(out, xmin, bwidth)
    assert_allclose(peaks, truth, rtol = 1e-2)

    peaks = ZeroCrossingPeakFinder(fitmode = 'gaussian')(out, xmin, bwidth)
    assert_allclose(peaks, truth, rtol = 1e-2)

def test_peakgroupby():
    u"testing group by peaks"
    events = [[1.0, 2.0, 10.0, 20.],
              [1.1, 2.1, 10.1, 20.],
              [1.2, 2.2, 10.2, 20.],
              [0.9, 1.9, 9.9,  15.],
              [0.8, 1.8, 9.8,  20.],
              [15.]]

    peaks = [1., 2., 10., 20.]
    res   = GroupByPeak(window = 1, mincount = 5)(peaks, events)

    inf   = np.iinfo('i4').max
    assert_equal([len(i) for i in res], [4]*5+[1])
    assert_equal(np.concatenate(res), [0, 1, 2, inf]*5+[inf])

if __name__ == '__main__':
    test_peakgroupby()
