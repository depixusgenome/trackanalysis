#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests interval detection"

import numpy    # type: ignore
from signalfilter.intervals import (DetectFlats, MergeFlats, FilterFlats,
                                    knownsigma)
import signalfilter.collapse as collapse

def test_detectflats():
    u"Tests flat stretches detection"
    inst  = DetectFlats(precision = 1., confidence = 0.1, window = 1)
    det   = lambda  i: tuple(inst(i))
    mksl  = lambda *i: tuple(slice(*j) for j in i)
    items = numpy.zeros((30,))
    thr   = knownsigma.threshold(True, inst.confidence, inst.precision,
                                 inst.window, inst.window)

    assert det([])    == tuple()
    assert det(items) == mksl((0, 30))

    items[10:] += thr
    items[20:] += thr
    items[21:] += thr
    assert det(items) == mksl((0, 10), (10,20), (21,30))

    items[0:2]  = (-2*thr, -thr)
    items[28:] += thr
    items[29:] += thr
    assert det(items) == mksl((2, 10), (10,20), (21,28))

def test_mergeflats():
    u"Tests flat stretches merging"
    inst  = MergeFlats(precision = 1., confidence = 0.1, isequal = True)
    det   = lambda  i, j: tuple(inst(i, j))
    mksl  = lambda *i: tuple(slice(*j) for j in i)
    items = numpy.zeros((30,))

    assert det([], mksl((0,30),)) == tuple()
    assert det([1], tuple())  == tuple()
    assert det(items, mksl((0, 30),))                == mksl((0,30))
    assert det(items, mksl((0, 10),(11,20),(22,30))) == mksl((0,30))
    assert det(items, mksl((2, 10),(11,20),(22,28))) == mksl((2,28))

    items[11:20] = 1000.
    assert det(items, mksl((0, 10),(11,20),(22,30))) == mksl((0, 10),(11,20),(22,30))

    items[:20] = 1000.
    assert det(items, mksl((0, 10),(11,20),(22,30))) == mksl((0,20),(22,30))

    items[11:] = 0.
    assert det(items, mksl((0, 10),(11,20),(22,30))) == mksl((0,10),(11,30))

def test_filterflats():
    u"Tests flat stretches filtering"
    det   = lambda  i, j, k: tuple(FilterFlats(edgelength = i, minlength = j)(k))
    mksl = lambda *i: tuple(slice(*j) for j in i)
    assert det(0, 0, mksl((0,0),(1,1)))                 == mksl((0,0), (1,1))
    assert det(0, 5, mksl((0,0),(1,1),(5,10)))          == mksl((5,10))
    assert det(1, 5, mksl((0,0),(1,1),(5,10), (20,30))) == mksl((21,29))

def test_collapse_intervals():
    u"Tests interval collapses"
    yvals  = numpy.zeros((100,5), dtype = numpy.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i
    xvals   = numpy.arange(100)+100

    # test horizontal lines
    inters  = [(xvals[5:10], yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = collapse.intervals(iter(inters))
    assert all(prof.count == 5)
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = numpy.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = collapse.intervals(iter(inters[1:-1]))
    assert all(prof.count == 3)
    numpy.testing.assert_allclose([-10,-5,0,5,10], prof.value, rtol = 1e-4)

    # test slanted lines + noise
    yvals[5:10,:] += numpy.random.rand(25).reshape((5,5))  # pylint: disable=no-member
    prof  = collapse.intervals(iter(inters[1:-1]))
    assert all(prof.count == 3)
    truth = numpy.mean(yvals[5:10,1:-1] - numpy.mean(yvals[5:10,1:-1], axis = 0), axis = 1)
    numpy.testing.assert_allclose(truth, prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = (xvals[15:25], yvals[15:25,1])
    prof      = collapse.intervals(iter(inters[:-1]))
    assert all(prof.count == ([3]*5+[0]*5+[1]*10))
    numpy.testing.assert_allclose(truth, prof.value[:5], rtol = 1e-5)
    assert all(prof.value[5:] == 0.)

def test_collapse_derivate():
    u"Tests derivate collapses"
    yvals  = numpy.zeros((100,5), dtype = numpy.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i
    xvals   = numpy.arange(100)+100

    # test horizontal lines
    inters  = [(xvals[5:10], yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = collapse.derivate(iter(inters))
    assert all(prof.count == ([5]*4+[0]))
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = numpy.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = collapse.derivate(iter(inters[1:-1]))
    assert all(prof.count == ([3]*4+[0]))
    numpy.testing.assert_allclose([-20,-15,-10,-5,0], prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = (xvals[15:25], yvals[15:25,1])
    prof      = collapse.derivate(iter(inters[:-1]))
    assert all(prof.count == ([3]*4+[0]*6+[1]*9+[0]))
    numpy.testing.assert_allclose([-20,-15,-10,-5,0], prof.value[:5], rtol = 1e-4)
    assert all(prof.value[5:] == 0.)
