#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
# pylint: disable=import-error,no-name-in-module
import numpy as np
from numpy.testing import assert_allclose

from data          import Beads
from signalfilter  import ForwardBackwardFilter, NonLinearFilter, hfsigma, nanhfsigma
from signalfilter.beadsubtraction import BeadSubtractionTask, BeadSubtractionProcessor

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

def test_subtract():
    "tests subtractions"
    assert_allclose(BeadSubtractionTask()([np.arange(5)]),   np.arange(5))
    assert_allclose(BeadSubtractionTask()([np.arange(5)]*5), np.arange(5))
    assert_allclose(BeadSubtractionTask()([np.arange(5), np.ones(5)]),
                    np.arange(5)*.5+.5)

    assert_allclose(BeadSubtractionTask()([np.arange(6), np.ones(5)]),
                    list(np.arange(5)*.5+.5)+[5])

    tmp = Beads(data = {0: np.arange(5), 1: np.ones(5),
                        2: np.zeros(5),  3: np.arange(5)*1.})
    cache = {}
    frame = BeadSubtractionProcessor.apply(tmp, cache, beads = [0, 1])
    assert set(frame.keys()) == {2, 3}
    assert_allclose(frame[2], -.5*np.arange(5)-.5)
    assert_allclose(cache[None],  .5*np.arange(5)+.5)

    ca0 = cache[None]
    res = frame[3]
    assert res is frame.data[3] # pylint: disable=unsubscriptable-object
    assert ca0 is cache[None]

if __name__ == '__main__':
    test_subtract()
