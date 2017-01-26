#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests interval detection"

import numpy    # type: ignore
from signalfilter.events import (SplitDetector, EventMerger, EventSelector,
                                 tocycles)
from signalfilter        import samples

def test_detectsplits():
    u"Tests flat stretches detection"
    inst  = SplitDetector(precision = 1., confidence = 0.1, window = 1)
    det   = lambda  i: tuple(tuple(j) for j in inst(i))
    items = numpy.zeros((30,))
    thr   = samples.normal.knownsigma.threshold(True, inst.confidence, inst.precision,
                                                inst.window, inst.window)

    assert det([])    == tuple()
    assert det(items) == ((0, 30),)

    items[10:] += thr
    items[20:] += thr
    items[21:] += thr
    assert det(items) == ((0, 10), (10,20), (21,30))

    items[0:2]  = (-2*thr, -thr)
    items[28:] += thr
    items[29:] += thr
    assert det(items) == ((2, 10), (10,20), (21,28))

    items       = numpy.zeros((30,))
    items[10:] += thr
    items[20:] += thr
    items[21:] += thr
    items[[0, 10, 25, 29]] = numpy.nan
    assert det(items) == ((0, 11), (11,20), (21,30))

def test_merge():
    u"Tests flat stretches merging"
    inst  = EventMerger(precision = 1., confidence = 0.1, isequal = True)
    det   = lambda  i, j: tuple(tuple(_) for _ in inst(i, numpy.array(j)))
    items = numpy.zeros((30,))

    assert det([], ((0,30),)) == tuple()
    assert det([1], tuple())  == tuple()
    assert det(items, ((0, 30),))                == ((0,30),)
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,30),)
    assert det(items, ((2, 10),(11,20),(22,28))) == ((2,28),)

    items[11:20] = 1000.
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0, 10),(11,20),(22,30))

    items[:20] = 1000.
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,20),(22,30))

    items[11:] = 0.
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,10),(11,30))

    items[11:] = 0.
    items[25]  = numpy.nan
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,10),(11,30))

def test_select():
    u"Tests flat stretches filtering"
    det   = lambda  i, j, k: tuple(tuple(_)
                                   for _ in EventSelector(edgelength = i, minlength = j)
                                   (numpy.array(k)))
    assert det(0, 0, ((0,0),(1,1)))                 == ((0,0), (1,1))
    assert det(0, 5, ((0,0),(1,1),(5,10)))          == ((5,10),)
    assert det(1, 5, ((0,0),(1,1),(5,10), (20,30))) == ((21,29),)

def test_tocycles():
    u"Tests interval assignment to cycles"
    starts = numpy.arange(10)*10
    inters = ((0,5), (3, 5), (0,15), (2, 21), (11,15), (11, 22), (16, 33),
              (80, 89), (80, 90), (80, 91), (83, 100), (83, 101), (90,120),
              (95, 95), (88, 88))
    inters = tuple(slice(*i) for i in inters)

    truth  = (0, 0, 0, 1, 1, 1, 2, 8, 8, 8, 9, 9, 9, 9, 8)
    vals   = tuple(i.cycle for i in tocycles(starts, inters))
    assert vals == truth

if __name__ == '__main__':
    test_merge()
