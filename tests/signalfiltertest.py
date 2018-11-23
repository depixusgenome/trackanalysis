#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
# pylint: disable=import-error,no-name-in-module
import numpy as np
from numpy.testing import assert_allclose

from signalfilter  import (ForwardBackwardFilter, NonLinearFilter, hfsigma, nanhfsigma,
                           nancount, nanthreshold)


def test_nl_bf_filters():
    u"Tests ForwardBackwardFilter, NonLinearFilter"
    for cls in (ForwardBackwardFilter, NonLinearFilter):
        args  = cls()

        arr   = np.arange(100, dtype = np.float32)
        truth = np.copy(arr)
        assert_allclose(truth[11:-11], args(arr)[11:-11])

        arr   = np.zeros(100, dtype = np.float32)
        truth = np.copy(arr)
        assert_allclose(truth, args(arr))

        arr     = np.zeros(100, dtype = np.float32)
        arr[50] = .1
        args(arr)
        assert_allclose(truth[:50], arr[:50], atol = 1e-7)
        assert_allclose(truth[51:], arr[51:], atol = 1e-7)

        arr   = np.zeros(100, dtype = np.float32)
        arr[45:55] = 1.
        truth = np.copy(arr)
        args(arr)
        assert_allclose(truth[:45], arr[:45])
        assert_allclose(truth[47:53], arr[47:53], atol = 1e-5)
        assert_allclose(truth[55:], arr[55:])

def test_hfsigma():
    u"Tests ForwardBackwardFilter, NonLinearFilter"
    arr = np.arange(10)*1.
    assert hfsigma(arr) == np.median(np.diff(arr))

    arr[0] = np.nan
    assert nanhfsigma(arr) == np.median(np.diff(arr[np.isfinite(arr)]))

    arr = 1.*np.arange(20)**2
    assert hfsigma(arr) == np.median(np.diff(arr))

    arr = np.insert(arr, range(0, 20, 2), np.nan)
    assert nanhfsigma(arr) == np.median(np.diff(arr[np.isfinite(arr)]))

def test_nancount():
    u"Tests ForwardBackwardFilter, NonLinearFilter"
    arr = np.arange(10)*1.
    out = np.zeros(10, dtype = 'i4')
    assert_allclose(nancount(arr, 1), out)
    out[-1] = 1
    assert_allclose(nancount(arr, 2), out)
    out[-2:] += 1
    assert_allclose(nancount(arr, 3), out)

    assert_allclose(nanthreshold(arr, 1, 1), np.zeros(10, dtype = 'bool'))
    assert_allclose(nanthreshold(arr, 2, 1), np.zeros(10, dtype = 'bool'))
    assert_allclose(nanthreshold(arr, 3, 1), np.zeros(10, dtype = 'bool'))


    arr[5] = np.NaN
    vals   = ([0, 0, 0, 0, 0, 1, 0, 0, 0, 0],
              [0, 0, 0, 0, 1, 1, 0, 0, 0, 1],
              [0, 0, 0, 1, 1, 1, 0, 0, 1, 2])
    assert_allclose(nancount(arr, 1), np.array(vals[0], dtype = 'i4'))
    assert_allclose(nancount(arr, 2), np.array(vals[1], dtype = 'i4'))
    assert_allclose(nancount(arr, 3), np.array(vals[2], dtype = 'i4'))
    assert_allclose(nanthreshold(arr, 1, 1), np.array(vals[0], dtype = 'bool'))
    assert_allclose(nanthreshold(arr, 2, 1), np.array(vals[1], dtype = 'bool'))
    assert_allclose(nanthreshold(arr, 3, 1), np.array(vals[2], dtype = 'bool'))

    arr[6] = np.NaN
    vals   = ([0, 0, 0, 0, 0, 1, 1, 0, 0, 0],
              [0, 0, 0, 0, 1, 2, 1, 0, 0, 1],
              [0, 0, 0, 1, 2, 2, 1, 0, 1, 2])
    assert_allclose(nancount(arr, 1), np.array(vals[0], dtype = 'i4'))
    assert_allclose(nancount(arr, 2), np.array(vals[1], dtype = 'i4'))
    assert_allclose(nancount(arr, 3), np.array(vals[2], dtype = 'i4'))
    assert_allclose(nanthreshold(arr, 1, 1), np.array(vals[0], dtype = 'bool'))
    assert_allclose(nanthreshold(arr, 2, 1), np.array(vals[1], dtype = 'bool'))
    assert_allclose(nanthreshold(arr, 3, 1), np.array(vals[2], dtype = 'bool'))
if __name__ == '__main__':
    test_hfsigma()
