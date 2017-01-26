#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
# pylint: disable=import-error,no-name-in-module
import numpy
from numpy.testing import assert_allclose

from signalfilter  import ForwardBackwardFilter, NonLinearFilter, hfsigma, nanhfsigma

def test_nl_bf_filters():
    u"Tests ForwardBackwardFilter, NonLinearFilter"
    for cls in (ForwardBackwardFilter, NonLinearFilter):
        args  = cls()

        arr   = numpy.arange(100, dtype = numpy.float32)
        truth = numpy.copy(arr)
        assert_allclose(truth[11:-11], args(arr)[11:-11])

        arr   = numpy.zeros(100, dtype = numpy.float32)
        truth = numpy.copy(arr)
        assert_allclose(truth, args(arr))

        arr     = numpy.zeros(100, dtype = numpy.float32)
        arr[50] = .1
        args(arr)
        assert_allclose(truth[:50], arr[:50], atol = 1e-7)
        assert_allclose(truth[51:], arr[51:], atol = 1e-7)

        arr   = numpy.zeros(100, dtype = numpy.float32)
        arr[45:55] = 1.
        truth = numpy.copy(arr)
        args(arr)
        assert_allclose(truth[:45], arr[:45])
        assert_allclose(truth[47:53], arr[47:53], atol = 1e-5)
        assert_allclose(truth[55:], arr[55:])

def test_hfsigma():
    u"Tests ForwardBackwardFilter, NonLinearFilter"
    arr = numpy.arange(10)*1.
    assert hfsigma(arr) == 0.

    arr[0] = numpy.nan
    assert nanhfsigma(arr) == 0.

    arr = 1.*numpy.arange(20)**2
    assert hfsigma(arr) == 6.

    arr = numpy.insert(arr, range(0, 20, 2), numpy.nan)
    assert nanhfsigma(arr) == 6.
