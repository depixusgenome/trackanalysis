#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"
import random
import numpy as np
from   numpy.testing import assert_allclose, assert_equal
from cordrift.collapse import (CollapseToMean,        CollapseByDerivate,
                               CollapseByMerging,
                               StitchByInterpolation, Profile, _getintervals,
                               StitchByDerivate, Range)

def test_collapse_to_mean():
    u"Tests interval collapses"
    yvals  = np.zeros((100,5), dtype = np.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i

    inst    = CollapseToMean(edge = None, filter = None)
    # test horizontal lines
    inters  = [Range(5, yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = inst(iter(inters))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 5)
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = np.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = inst(iter(inters[1:-1]))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 3)
    assert_allclose([-10,-5,0,5,10], prof.value, rtol = 1e-4)

    # test slanted lines + noise
    yvals[5:10,:] += np.random.rand(25).reshape((5,5))  # pylint: disable=no-member
    prof           = inst(iter(inters[1:-1]))
    assert all(prof.count == 3)
    truth = np.mean(yvals[5:10,1:-1] - np.mean(yvals[5:10,1:-1], axis = 0), axis = 1)
    assert_allclose(truth, prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = Range(15, yvals[15:25,1])
    prof      = inst(iter(inters[:-1]))
    assert all(prof.count == ([3]*5+[0]*5+[1]*10))
    assert_allclose(truth, prof.value[:5], rtol = 1e-5, atol = 1e-5)
    assert all(prof.value[5:] == 0.)

def test_collapse_by_merging():
    u"Tests interval collapses"
    yvals  = np.zeros((100,5), dtype = np.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i

    inst   = CollapseByMerging(edge = None, filter = None)

    # test horizontal lines
    inters  = [Range(5, yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = inst(iter(inters))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 5)
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = np.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = inst(iter(inters[1:-1]))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 3)
    assert_allclose([-10,-5,0,5,10], prof.value, rtol = 1e-4)

    # test slanted lines + noise
    yvals[5:10,:] += np.random.rand(25).reshape((5,5))  # pylint: disable=no-member
    prof           = inst(iter(inters[1:-1]))
    assert all(prof.count == 3)
    truth = np.mean(yvals[5:10,1:-1] - np.mean(yvals[5:10,1:-1], axis = 0), axis = 1)
    assert_allclose(truth-truth[0], prof.value-prof.value[0], rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = Range(15, yvals[15:25,1])
    prof      = inst(iter(inters[:-1]))
    assert all(prof.count == ([3]*5+[0]*5+[1]*10))
    assert_allclose(truth-truth[0], prof.value[:5]-prof.value[0], rtol = 1e-5)
    assert all(prof.value[5:] == 0.)

def test_collapse_by_derivate():
    u"Tests derivate collapses"
    yvals  = np.zeros((100,5), dtype = np.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i

    # test horizontal lines
    inters  = [Range(5, yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = CollapseByDerivate.run(iter(inters), edge = None, filter = None)
    assert all(prof.count == ([5]*4+[0]))
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = np.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = CollapseByDerivate.run(iter(inters[1:-1]), edge = None)
    assert all(prof.count == ([3]*4+[0]))
    assert_allclose([-20,-15,-10,-5,0], prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = Range(15, yvals[15:25,1])
    prof      = CollapseByDerivate.run(iter(inters[:-1]), edge = None)
    assert all(prof.count == ([3]*4+[0]*6+[1]*9+[0]))
    assert_allclose([-20,-15,-10,-5,0], prof.value[:5], rtol = 1e-4)
    assert all(prof.value[5:] == 0.)

def test_getinter():
    u"Tests _getintervals"
    fge = lambda x: _getintervals(np.array(x), 2, np.greater_equal)
    flt = lambda x: _getintervals(np.array(x), 2, np.less)
    assert_equal(flt([2]*5+[1]*5),       [[5,10]])
    assert_equal(fge([2]*5+[1]*5),       [[0,5]])
    assert_equal(flt([1]*5+[2]*5+[1]*5), [[0,5], [10,15]])
    assert_equal(fge([1]*5+[2]*5+[1]*5), [[5,10]])

def test_stitchbyinterpolation():
    u"Tests StitchByInterpolation"
    def _test(power = 1, left = False, right = False):
        prof          = Profile(60)
        prof.count[:] = 10
        prof.value = np.arange(len(prof), dtype = 'f4') ** power
        if left:
            prof.value[0] = 1
            prof.count[0] = 0
        if right:
            prof.value[-1] = prof.value[-2]
            prof.count[-1] = 0

        truth = np.array(prof.value)

        for i in range(10, len(prof), 10):
            prof.value[i:]                += random.randint(-100, 100)
            prof.count[i-i//10:i+i//10-1]  = 0

        stitched = StitchByInterpolation.run(prof,
                                             fitlength   = 3,
                                             fitorder    = power,
                                             minoverlaps = 5)
        assert_allclose(stitched.value, truth)

    for order in (1, 2):
        for left in (False, True):
            for right in (False, True):
                _test(order, left, right)

def test_stitchbyderivate():
    u"Tests StitchByDerivate"

    def _test(left = False, right = False):
        prof          = Profile(60)
        prof.count[:] = 10
        prof.value = np.arange(len(prof), dtype = 'f4')
        data      = np.empty((9, 60), dtype = np.float32)
        data[:4]  = np.arange(60)**2
        data[4,:] = np.arange(len(prof), dtype = 'f4')
        data[-4:] = -np.arange(60)**3

        items     = [Range(0, i) for i in data]
        if left:
            prof.count[0] = 0
        if right:
            prof.count[-1] = 0

        truth = np.array(prof.value)

        for i in range(10, len(prof), 10):
            prof.value[i:]                += random.randint(-100, 100)
            prof.count[i-i//10:i+i//10-1]  = 0

        stitched = StitchByDerivate.run(prof, items, minoverlaps = 5)
        assert_allclose(stitched.value, truth)

    _test(True, False)
    for left in (False, True):
        for right in (False, True):
            _test(left, right)

if __name__ == '__main__':
    test_stitchbyinterpolation()
