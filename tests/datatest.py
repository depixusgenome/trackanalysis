#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests data access """
import numpy
from   legacy import readtrack   # pylint: disable=import-error,no-name-in-module
import data
from   testdata import path

# pylint: disable=no-self-use

class TestBeadIteration:
    u"tests opening a trackfile"
    def test_iterkeys(self):
        u"tests wether keys are well listed"
        track = data.Track(path = path("small_legacy"))
        assert tuple(track.beads.keys())                    == tuple(range(92))
        assert tuple(i for i, _ in track.beads)             == tuple(range(92))
        assert tuple(track.beads.selecting(all).keys())     ==  tuple(range(92))
        assert tuple(track.beads.selecting(None).keys())    == tuple(range(92))

        sel = track.beads
        assert tuple(track.beads.selecting([2,3,2]).keys()) == (2,3,2)
        assert tuple(i for i,_ in sel.selecting([2,3,2]))   == (2,3,2)
        assert tuple(sel.selecting(2, clear = True).keys()) == (2,)
        assert tuple(track.beads
                     .selecting(range(50))
                     .discarding(range(1,48))
                     .keys())                               == (0, 48, 49)
        assert tuple(track.beads
                     .selecting(2)
                     .selecting([2,3])
                     .keys())                               == (2,2,3)

class TestCycleIteration:
    u"tests opening a trackfile"
    def test_iterkeys(self):
        u"tests wether keys are well listed"
        track = data.Track(path = path("big_legacy"))
        assert (tuple(track.cycles.selecting(0).keys())
                == tuple((i,0) for i in range(39)))
        assert (tuple(track.cycles.selecting((0,0)).keys())
                == ((0,0),))
        assert (tuple(track.cycles.selecting([(0,all)]).keys())
                == tuple((0,i) for i in range(102)))
        assert (tuple(track.cycles
                      .selecting((0,all))
                      .discarding((0,i) for i in range(10, 200))
                      .keys())
                == tuple((0,i) for i in range(10)))

        truth = readtrack(path("big_legacy"))[0]
        for _, vals in track.cycles.selecting((0,1)):
            assert numpy.array_equal(vals, truth[1166-678:1654-678])

        for _, vals in track.cycles.withfirst(2).withlast(3).selecting((0,1)):
            assert numpy.array_equal(vals, truth[1206-678:1275-678])

    def test_lazy(self):
        u"tests what happens when using lazy mode"
        truth = readtrack(path("big_legacy"))[0]
        for _, vals in data.Cycles(track    = lambda:data.Track(path = path("big_legacy")),
                                   first    = lambda:2,
                                   last     = lambda:3,
                                   selected = lambda:[(0,1)]):
            assert numpy.array_equal(vals, truth[1206-678:1275-678])

    def test_nocopy(self):
        u"tests that data by default is not copied"
        track = data.Track(path = path("big_legacy"))
        vals1 = numpy.arange(1)
        for _, vals1 in data.Cycles(track   = track,
                                    first    = 2,
                                    last     = 3,
                                    selected = (0,1)):
            pass

        vals2 = numpy.arange(2)
        for _, vals2 in data.Cycles(track    = track,
                                    first    = 2,
                                    last     = 3,
                                    selected = (0,1)):
            pass

        assert numpy.array_equal(vals1, vals2)
        vals1[:] = 0
        assert numpy.array_equal(vals1, vals2)

    def test_copy(self):
        u"tests that data can be copied"
        track = data.Track(path = path("big_legacy"))
        vals1 = numpy.arange(1)
        for _, vals1 in data.Cycles(track   = track,
                                    first    = 2,
                                    last     = 3,
                                    selected = (0,1)):
            pass

        vals2 = numpy.arange(2)
        for _, vals2 in data.Cycles(track    = track,
                                    first    = 2,
                                    last     = 3,
                                    copy     = True,
                                    selected = (0,1)):
            pass

        assert numpy.array_equal(vals1, vals2)
        vals1[:] = 0
        assert not numpy.array_equal(vals1, vals2)
