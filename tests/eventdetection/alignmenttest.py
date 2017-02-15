#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cycle alignments"
import numpy as np

from eventdetection.alignment import ExtremumAlignment, CorrelationAlignment

def test_minmaxalign():
    u"align on min/max value"
    data = np.zeros((5,25), dtype = np.float32)
    for i in range(5):
        data[i,:] = np.arange(25)+i*1.
    truth  = np.array([2., 1., 0., -1., -2.])

    for tpe in 'min', 'max':
        np.testing.assert_allclose(ExtremumAlignment.run(data, mode = tpe), truth)

def test_correlationalignment():
    u"align on best correlation"
    data = [np.zeros((100,)) for i in range(3)]
    for i in range(3):
        data[i][20+i] = 1.
        data[i][50+i] = 1.

    corr = lambda f, a, b, c, d, e: (CorrelationAlignment.run(f,
                                                              oversampling  = a,
                                                              maxcorr       = b,
                                                              nrepeats      = c,
                                                              kernel_window = d,
                                                              kernel_width  = e))

    biases = corr(data, 1, 2, 1, 0, .1)
    np.testing.assert_allclose(biases, [1., 0., -1.])

    biases = corr(data, 5, 2, 1, 3, 2.)
    np.testing.assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)

if __name__ == '__main__':
    test_minmaxalign()
