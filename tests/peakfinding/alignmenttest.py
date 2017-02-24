#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cycle alignments"
import numpy as np

from peakfinding.alignment  import PeakCorrelationAlignment
from simulator              import randpeaks

CORR = lambda f, a, b, c, d, e: (PeakCorrelationAlignment.run(f,
                                                              subpixel      = None,
                                                              precision     = 1.,
                                                              oversampling  = a,
                                                              maxmove       = b,
                                                              factors       = [1.]*c,
                                                              kernel_window = d,
                                                              kernel_width  = e))

def test_correlationalignment():
    u"align on best correlation"
    data = [[20, 50], [21, 51], [22, 52]]


    biases = CORR(data, 1, 5, 1, 0, .1)
    np.testing.assert_allclose(biases, [1., 0., -1.])

    biases = CORR(data, 5, 5, 1, 3, 2.)
    np.testing.assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)

def test_randcorrelationalignment():
    u"align on best correlation"
    peaks, labels  = randpeaks(100,
                               peaks    = [20, 50, 60, 90],
                               rates    = .7,
                               bias     = 2.,
                               brownian = None,
                               stretch  = None,
                               seed     = 0,
                               labels   = 'range')
    biases = CORR(peaks, 5, 5, 6, 3, 2.)
    res    = peaks+biases

    orig   = np.array([np.concatenate([pks[labs == i] for pks, labs in zip(peaks, labels)])
                       for i in range(4)])
    cured  = np.array([np.concatenate([pks[labs == i] for pks, labs in zip(res, labels)])
                       for i in range(4)])

    cstd   = np.array([i.std() for i in cured])
    ostd   = np.array([i.std() for i in orig])
    assert  all(cstd < ostd/18.)

if __name__ == '__main__':
    test_randcorrelationalignment()
