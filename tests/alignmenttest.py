#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cycle alignments"
import numpy as np

import signalfilter.alignment as alignment

def test_minmaxalign():
    u"align on min/max value"
    data = np.zeros((5,25), dtype = np.float32)
    for i in range(5):
        data[i,:] = np.arange(25)+i*1.
    truth  = np.array([2., 1., 0., -1., -2.])

    for tpe in 'min', 'max':
        np.testing.assert_allclose(alignment.extremum(data, tpe), truth)

def test_correlationalignment():
    u"align on best correlation"
    data = [np.zeros((100,)) for i in range(3)]
    for i in range(3):
        data[i][20+i] = 1.
        data[i][50+i] = 1.

    biases = alignment.correlation(data, 1, 2, 1, 0, .1)
    np.testing.assert_allclose(biases, [1., 0., -1.])

    biases = alignment.correlation(data, 5, 2, 1, 2, 3.)
    np.testing.assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)
