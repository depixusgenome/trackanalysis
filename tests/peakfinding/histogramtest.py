#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests histogram  creation and analysis"
import numpy as np
from numpy.testing import assert_equal, assert_allclose

from peakfinding.histogram import Histogram

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

if __name__ == '__main__':
    test_histogram()
