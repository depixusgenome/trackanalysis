#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests data access """
from   pathlib      import Path
from   itertools    import product
import numpy as np

from   legacy           import readtrack   # pylint: disable=import-error,no-name-in-module
import data
from   data.trackitems  import Items
from   data.trackio     import LegacyGRFilesIO
from   testingcore      import path as utpath, getmonkey

# pylint: disable=missing-docstring,protected-access
class _MyItem(Items):
    def __init__(self, vals):
        super().__init__()
        self.vals = vals

    def __getitem__(self, key):
        return self.vals[key]

    def keys(self, sel = None, beadsonly = None):
        assert sel is None
        assert beadsonly is None
        yield from self.vals.keys()

def test_beaditerkeys():
    u"tests wether keys are well listed"
    track = data.Track(path = utpath("small_legacy"), beadsonly = False)
    beads = lambda: data.Beads(track = track, data = _MyItem(track.data))
    vals = set(tuple(range(92))+ ('zmag', 't'))
    assert set(beads().keys())                 == vals
    assert set(i for i, _ in beads())          == vals
    assert set(beads().selecting(['t', 0]).withbeadsonly().keys()) == {0}
    assert set(beads().withbeadsonly().keys()) == (vals-{'zmag', 't'})
    assert set(beads().selecting(all).keys())  == vals
    assert set(beads().selecting(None).keys()) == vals
    assert isinstance(beads()['t'], np.ndarray)
    assert isinstance(beads()[0],   np.ndarray)

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

def test_cycles_iterkeys():
    u"tests wether keys are well listed"
    track = data.Track(path = utpath("big_legacy"), beadsonly = False)
    cycs  = lambda: data.Cycles(track = track, data = _MyItem(track.data))
    cids  = lambda _: set(tuple((i,_) for i in range(39)) + (('zmag', _), ('t', _)))
    bids  = lambda _: set((_,i) for i in range(102))
    assert set  (cycs().selecting(0).keys())         == cids(0)
    assert tuple(cycs().selecting((0,0)).keys())     == ((0,0),)
    assert set  (cycs()[...,0].keys())               == cids(0)
    assert set  (cycs()[0,...].keys())               == bids(0)
    assert set  (cycs()['zmag',...].keys())          == bids('zmag')
    assert set(i[0] for i in (cycs()
                              .selecting([('t',...), (0,...)])
                              .withbeadsonly().keys())) == {0}
    assert {"t", "zmag"} - set(i[0] for i in cycs().withbeadsonly().keys())  == {'t', 'zmag'}

    assert (tuple(cycs()
                  .selecting((0,all))
                  .discarding((0,i) for i in range(10, 200))
                  .keys())
            == tuple((0,i) for i in range(10)))

    assert isinstance(cycs()[('zmag',0)], np.ndarray)

    truth = readtrack(utpath("big_legacy"))[0]
    for _, vals in cycs().selecting((0,1)):
        assert np.array_equal(vals, truth[1166-678:1654-678])

    for _, vals in cycs().withfirst(2).withlast(3).selecting((0,1)):
        assert np.array_equal(vals, truth[1206-678:1275-678])

def test_cycles_mixellipsisnumbers():
    "mixing ellipis and lists of numbers in the indexes"
    track = data.Track(path = utpath("big_legacy"), beadsonly = False)
    beads = lambda: data.Beads(track = track, data = _MyItem(track.data))
    assert (tuple(beads()[..., np.arange(5)].selected)
            == tuple((..., i) for i in range(5)))

    assert (tuple(beads()[np.arange(5), ...].selected)
            == tuple((i, ...) for i in range(5)))

    assert (tuple(beads()[np.arange(5), [3, 5]].selected)
            == tuple(product(range(5), [3, 5])))


def test_cycles_cancyclefromcycle():
    u"A cycle can contain a cycle as data"
    track = data.Track(path = utpath("big_legacy"))
    cycs  = data.Cycles(track = track, data = _MyItem(track.data))
    cyc   = data.Cycles(track = track, data = cycs)
    assert set(cyc.keys()) == set(track.cycles.keys())
    assert set(cyc[...,0].keys()) == set(track.cycles[...,0].keys())
    assert np.array_equal(cyc[0,0], track.cycles[0,0])

    def _act1(col):
        col[1][:] = 5.
        return col

    def _act2(col):
        col[1][:] = all(x == 5. for x in col[1])
        return col

    cyc = (data.Cycles(track = track, data = track.cycles.withaction(_act1))
           .withaction(_act2))
    assert all(x == 1. for x in cyc[0,0])

def test_cycles_lazy():
    u"tests what happens when using lazy mode"
    truth = readtrack(utpath("big_legacy"))[0]
    for _, vals in data.Cycles(track    = lambda:data.Track(path = utpath("big_legacy")),
                               first    = lambda:2,
                               last     = lambda:3,
                               selected = lambda:[(0,1)]):
        assert np.array_equal(vals, truth[1206-678:1275-678])

def test_cycles_nocopy():
    u"tests that data by default is not copied"
    track = data.Track(path = utpath("big_legacy"))
    vals1 = np.arange(1)
    for _, vals1 in data.Cycles(track   = track,
                                first    = 2,
                                last     = 3,
                                selected = (0,1)):
        pass

    vals2 = np.arange(2)
    for _, vals2 in data.Cycles(track    = track,
                                first    = 2,
                                last     = 3,
                                selected = (0,1)):
        pass

    assert np.array_equal(vals1, vals2)
    vals1[:] = 0
    assert np.array_equal(vals1, vals2)

def test_cycles_copy():
    u"tests that data can be copied"
    track = data.Track(path = utpath("big_legacy"))
    vals1 = np.arange(1)
    for _, vals1 in data.Cycles(track   = track,
                                first    = 2,
                                last     = 3,
                                selected = (0,1)):
        pass

    vals2 = np.arange(2)
    for _, vals2 in data.Cycles(track    = track,
                                first    = 2,
                                last     = 3,
                                copy     = True,
                                selected = (0,1)):
        pass

    assert np.array_equal(vals1, vals2)
    vals1[:] = 0
    assert not np.array_equal(vals1, vals2)

def test_loadgrdir():
    paths = utpath("big_legacy"), utpath("big_grlegacy")
    for time in range(2):
        if time == 1:
            paths = paths[:1] + tuple(str(i) for i in Path(paths[1]).iterdir()
                                      if i.suffix == '.gr')
            paths = paths[5:] + paths[:5]
        track = data.Track(path = paths)
        keys  = {0, 10, 12, 13, 14, 16, 17, 18, 1, 21, 22, 23,
                 24, 25, 26, 27, 28, 29, 2, 34, 35, 37, 3, 4, 6, 7}
        assert set(track.beadsonly.keys()) == keys

        keys  = {17, 23, 41, 14, 31, 45, 18, 37, 44,  7, 32,  6, 48, 22, 24, 47, 28,
                 19, 30, 25, 43, 42,  8, 26, 16, 12,  9, 33, 35, 27,  3, 10, 21, 15,
                 34, 29, 13,  5,  4, 20, 46, 11}
        keys  = {i-3 for i in keys}
        good  = {i[1] for i, j in track.cycles[28,...] if not np.all(np.isnan(j))}
        assert good == keys
        assert len(good) < track.ncycles

def test_findgrdir():
    paths = str(Path(utpath("big_legacy")).parent/'*.trk'), utpath("big_grlegacy")
    track = data.Track(path = paths)
    keys  = {0, 10, 12, 13, 14, 16, 17, 18, 1, 21, 22, 23,
             24, 25, 26, 27, 28, 29, 2, 34, 35, 37, 3, 4, 6, 7}
    assert set(track.beadsonly.keys()) == keys

    paths = str(Path(utpath("big_legacy")).parent/'test*.trk'), utpath("big_grlegacy")
    track = data.Track(path = paths)
    keys  = {0, 10, 12, 13, 14, 16, 17, 18, 1, 21, 22, 23,
             24, 25, 26, 27, 28, 29, 2, 34, 35, 37, 3, 4, 6, 7}
    assert set(track.beadsonly.keys()) == keys

def test_scancgr(monkeypatch):
    "tests LegacyGRFilesIO.scancgr"
    assert LegacyGRFilesIO.scancgr("dummy", "dummy") == ((), (), ())

    directory        = Path(utpath(None))
    pairs, grs, trks = LegacyGRFilesIO.scancgr(directory, directory)
    assert (pairs, grs) == ((), ())
    assert sorted(trks) == sorted(Path(directory).glob("*.trk"))

    monkeypatch.setattr(LegacyGRFilesIO, '_LegacyGRFilesIO__CGR', 'CTGT_selection')
    pairs, grs, trks = LegacyGRFilesIO.scancgr(directory, directory)
    assert len(grs) == 0
    assert pairs    == ((directory/'test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk',
                         directory/'CTGT_selection'),)
    assert len(trks) == len(tuple(Path(directory).glob("*.trk"))) - len(pairs)

if __name__ == '__main__':
    test_scancgr(getmonkey())
