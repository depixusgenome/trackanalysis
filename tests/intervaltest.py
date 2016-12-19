#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests interval detection"

import numpy
from signalfilter.intervals import DetectFlats, MergeFlats, FilterFlats, knownsigma

def test_detectflats():
    u"Tests flat stretches detection"
    inst  = DetectFlats(uncertainty = 1., confidence = 0.1, window = 1)
    det   = lambda  i: tuple(inst(i))
    mksl = lambda *i: tuple(slice(*j) for j in i)
    items = numpy.zeros((30,))
    thr   = knownsigma.threshold(True, inst.confidence, inst.uncertainty,
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
    inst  = MergeFlats(uncertainty = 1., confidence = 0.1, isequal = True)
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
