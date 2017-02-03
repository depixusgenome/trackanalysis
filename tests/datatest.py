#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests data access """
import numpy
from   legacy       import readtrack   # pylint: disable=import-error,no-name-in-module
import data
from   data.trackitems  import Items
from   testingcore      import path

# pylint: disable=no-self-use, missing-docstring,protected-access
class _MyItem(Items):
    def __init__(self, vals):
        super().__init__()
        self.vals = vals

    def __getitem__(self, key):
        return self.vals[key]

    def keys(self, sel = None):
        assert sel is None
        yield from self.vals.keys()

class TestBeadIteration:
    u"tests opening a trackfile"
    def test_iterkeys(self):
        u"tests wether keys are well listed"
        track = data.Track(path = path("small_legacy"))
        beads = lambda: data.Beads(track = track, data = _MyItem(track.data))
        vals = set(tuple(range(92)) + ('zmag', 't'))
        assert set(beads().keys())                 == vals
        assert set(i for i, _ in beads())          == vals
        assert set(beads().selecting(all).keys())  == vals
        assert set(beads().selecting(None).keys()) == vals
        assert isinstance(beads()['t'], numpy.ndarray)
        assert isinstance(beads()[0],   numpy.ndarray)

        sel = track.beads
        assert tuple(beads().selecting([2,3,2]).keys()) == (2,3,2)
        assert tuple(i for i,_ in sel.selecting([2,3,2]))   == (2,3,2)
        assert tuple(sel.selecting(2, clear = True).keys()) == (2,)
        assert tuple(beads()
                     .selecting(range(50))
                     .discarding(range(1,48))
                     .keys())                               == (0, 48, 49)
        assert tuple(beads()
                     .selecting(2)
                     .selecting([2,3])
                     .keys())                               == (2,2,3)

class TestCycleIteration:
    u"tests opening a trackfile"
    def test_iterkeys(self):
        u"tests wether keys are well listed"
        track = data.Track(path = path("big_legacy"))
        cycs  = lambda: data.Cycles(track = track, data = _MyItem(track.data))
        cids  = lambda _: set(tuple((i,_) for i in range(39)) + (('zmag', _), ('t', _)))
        bids  = lambda _: set((_,i) for i in range(102))
        assert set  (cycs().selecting(0).keys())         == cids(0)
        assert tuple(cycs().selecting((0,0)).keys())     == ((0,0),)
        assert set  (cycs()[...,0].keys())               == cids(0)
        assert set  (cycs()[0,...].keys())               == bids(0)
        assert set  (cycs()['zmag',...].keys())          == bids('zmag')

        assert (tuple(cycs()
                      .selecting((0,all))
                      .discarding((0,i) for i in range(10, 200))
                      .keys())
                == tuple((0,i) for i in range(10)))

        assert isinstance(cycs()[('zmag',0)], numpy.ndarray)

        truth = readtrack(path("big_legacy"))[0]
        for _, vals in cycs().selecting((0,1)):
            assert numpy.array_equal(vals, truth[1166-678:1654-678])

        for _, vals in cycs().withfirst(2).withlast(3).selecting((0,1)):
            assert numpy.array_equal(vals, truth[1206-678:1275-678])

    def test_cancyclefromcycle(self):
        u"A cycle can contain a cycle as data"
        track = data.Track(path = path("big_legacy"))
        cycs  = data.Cycles(track = track, data = _MyItem(track.data))
        cyc   = data.Cycles(track = track, data = cycs)
        assert set(cyc.keys()) == set(track.cycles.keys())
        assert set(cyc[...,0].keys()) == set(track.cycles[...,0].keys())
        assert numpy.array_equal(cyc[0,0], track.cycles[0,0])

        def _act1(col):
            col[1][:] = 5.
            return col

        def _act2(col):
            col[1][:] = all(x == 5. for x in col[1])
            return col

        cyc = (data.Cycles(track = track, data = track.cycles.withaction(_act1))
               .withaction(_act2))
        assert all(x == 1. for x in cyc[0,0])

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

if __name__ == '__main__':
    TestCycleIteration().test_iterkeys()
