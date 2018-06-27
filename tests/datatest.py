#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Tests data access """
from   pathlib      import Path
from   itertools    import product
from   typing       import cast, Iterable
import tempfile
import numpy as np
from   numpy.testing    import assert_equal, assert_allclose

from   legacy           import readtrack   # pylint: disable=import-error,no-name-in-module
import data
from   data.views       import ITrackView
from   data.trackio     import LegacyGRFilesIO, savetrack, PickleIO, LegacyTrackIO
from   data.track       import FoV, Track
from   data.trackops    import concatenatetracks, selectcycles, dropbeads, clone
from   data.tracksdict  import TracksDict
from   testingcore      import path as utpath

# pylint: disable=missing-docstring,protected-access
class _MyItem(ITrackView):
    def __init__(self, vals):
        super().__init__()
        self.vals = vals

    def __getitem__(self, key):
        return self.vals[key]

    track = property(lambda self: data.Track(data = self.vals))

    def __iter__(self):
        return iter(self.vals)

    def __copy__(self):
        return _MyItem(self.vals)

    def keys(self, sel = None):
        assert sel is None
        yield from self.vals.keys()

def test_beaditerkeys():
    "tests wether keys are well listed"
    track = data.Track(path = utpath("small_legacy"))
    beads = lambda: data.Beads(track = track, data = _MyItem(track.data))
    vals  = {i for i in range(92)}

    assert len(tuple(beads().keys()))                 == len(vals)
    assert len(tuple(i for i, _ in beads()))          == len(vals)
    assert len(tuple(beads().selecting(all).keys()))  == len(vals)
    assert len(tuple(beads().selecting(None).keys())) == len(vals)
    assert len(tuple(beads()[:].keys())) == len(vals)
    assert len(tuple(beads()[:2].keys())) == len({0, 1})
    assert len(tuple(beads()[:2][1:5].keys())) == len({1}) # pylint: disable=unsubscriptable-object

    assert set(beads().keys())                 == vals
    assert set(i for i, _ in beads())          == vals
    assert set(beads().selecting(all).keys())  == vals
    assert set(beads().selecting(None).keys()) == vals
    assert set(beads()[:].keys()) == vals
    assert set(beads()[:2].keys()) == {0, 1}
    assert set(beads()[:2][1:5].keys()) == {1} # pylint: disable=unsubscriptable-object
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
    "tests wether keys are well listed"
    track = data.Track(path = utpath("big_legacy"))
    cycs  = lambda: data.Cycles(track = track, data = _MyItem(track.data))
    cids  = lambda _: {(i,_) for i in range(39)}
    bids  = lambda _: {(_,i) for i in range(102)}
    assert len(tuple(cycs().selecting(0).keys()))  == len(bids(0))
    assert len(tuple(cycs()[:,0].keys()))          == len(cids(0))
    assert len(tuple(cycs()[...,0].keys()))        == len(cids(0))
    assert len(tuple(cycs()[...,0][1,...].keys())) == len({(1,0)})
    assert len(tuple(cycs()[:1,0].keys()))         == len({i for i in cids(0) if i[0] == 0})
    assert len(tuple(cycs()[0,...].keys()))        == len(bids(0))
    assert len(tuple(cycs()[0,:].keys()))          == len(bids(0))
    assert len(tuple(cycs()[0,2:5].keys()))        == len({i for i in bids(0) if 2<= i[1] < 5})

    assert set  (cycs().selecting(0).keys())     == bids(0)
    assert tuple(cycs().selecting((0,0)).keys()) == ((0,0),)
    assert set  (cycs()[:,0].keys())             == cids(0)
    assert set  (cycs()[...,0].keys())           == cids(0)
    assert set  (cycs()[...,0][1,...].keys())    == {(1,0)}
    assert set  (cycs()[:1,0].keys())            == {i for i in cids(0) if i[0] == 0}
    assert set  (cycs()[0,...].keys())           == bids(0)
    assert set  (cycs()[0,:].keys())             == bids(0)
    assert set  (cycs()[0,2:5].keys())           == {i for i in bids(0) if 2<= i[1] < 5}
    assert set(i[0] for i in (cycs()
                              .selecting([(0,...)]).keys())) == {0}

    assert (tuple(cycs()
                  .selecting((0,all))
                  .discarding((0,i) for i in range(10, 200))
                  .keys())
            == tuple((0,i) for i in range(10)))

    truth = readtrack(utpath("big_legacy"))[0]
    for _, vals in cycs().selecting((0,1)):
        assert np.array_equal(vals, truth[1166-678:1654-678])

    for _, vals in cycs().withfirst(2).withlast(3).selecting((0,1)):
        assert np.array_equal(vals, truth[1206-678:1275-678])

def test_cycles_iterkeys2():
    "tests wether keys are well listed"
    track = data.Track(path = utpath("big_legacy"))
    beads = track.beads.withcycles(range(5, 15))
    cycles = beads.new(data.Cycles)
    assert len(tuple(cycles[0, ...])) == 10
    assert set(cycles[0,...].keys()) == {(0, i) for i in range(5, 15)}

    beads = track.beads.withcycles(...)
    cycles = beads.new(data.Cycles)
    assert len(tuple(cycles[0, ...])) == 102

def test_cycles_mixellipsisnumbers():
    "mixing ellipis and lists of numbers in the indexes"
    track = data.Track(path = utpath("big_legacy"))
    beads = lambda: data.Beads(track = track, data = _MyItem(track.data))
    assert (tuple(beads()[..., np.arange(5)].selected)
            == tuple((..., i) for i in range(5)))

    assert (tuple(beads()[np.arange(5), ...].selected)
            == tuple((i, ...) for i in range(5)))

    assert (tuple(beads()[np.arange(5), [3, 5]].selected)
            == tuple(product(range(5), [3, 5])))

def test_cycles_cancyclefromcycle():
    "A cycle can contain a cycle as data"
    track = data.Track(path = utpath("big_legacy"))
    cycs  = data.Cycles(track = track, data = _MyItem(track.data))
    cyc   = data.Cycles(track = track, data = cycs)
    assert set(cyc.keys()) == set(track.cycles.keys())
    assert set(cyc[...,0].keys()) == set(track.cycles[...,0].keys())
    assert np.array_equal(cyc[0,0], track.cycles[0,0])

    def _act1(_, col):
        col[1][:] = 5.
        return col

    def _act2(_, col):
        col[1][:] = all(x == 5. for x in col[1])
        return col

    cyc = (data.Cycles(track = track, data = track.cycles.withaction(_act1))
           .withaction(_act2))
    assert all(x == 1. for x in cyc[0,0])

def test_cycles_lazy():
    "tests what happens when using lazy mode"
    truth = readtrack(utpath("big_legacy"))[0]
    for _, vals in data.Cycles(track    = lambda _:data.Track(path = utpath("big_legacy")),
                               first    = lambda _:2,
                               last     = lambda _:3,
                               selected = lambda _:[(0,1)]):
        assert np.array_equal(vals, truth[1206-678:1275-678])

def test_cycles_nocopy():
    "tests that data by default is not copied"
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
    "tests that data can be copied"
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
            paths = (paths[:1]  # type: ignore
                     + tuple(str(i) for i in Path(cast(str, paths[1])).iterdir()
                             if i.suffix == '.gr'))
            paths = paths[5:] + paths[:5] # type:ignore
        track = data.Track(path = paths)
        keys  = {0, 10, 12, 13, 14, 16, 17, 18, 1, 21, 22, 23,
                 24, 25, 26, 27, 28, 29, 2, 34, 35, 37, 3, 4, 6, 7}
        assert set(track.beads.keys()) == keys

        keys  = {17, 23, 41, 14, 31, 45, 18, 37, 44,  7, 32,  6, 48, 22, 24, 47, 28,
                 19, 30, 25, 43, 42,  8, 26, 16, 12,  9, 33, 35, 27,  3, 10, 21, 15,
                 34, 29, 13,  5,  4, 20, 46, 11}
        keys  = {i-3 for i in keys}
        good  = {i[1] for i, j in track.cycles[28,...] if not np.all(np.isnan(j))}
        assert good == keys
        assert len(good) < track.ncycles
        assert all(np.isfinite(j).sum() == 0 for _, j in track.cycles.withphases(0)[28,...])

def test_findgrdir():
    trkpath = str(Path(cast(str, utpath("big_legacy"))).parent/'*.trk')
    paths   = trkpath, utpath("big_grlegacy")
    track   = data.Track(path = paths)
    keys    = {0, 10, 12, 13, 14, 16, 17, 18, 1, 21, 22, 23,
               24, 25, 26, 27, 28, 29, 2, 34, 35, 37, 3, 4, 6, 7}
    assert set(track.beads.keys()) == keys

    trkpath = str(Path(cast(str, utpath("big_legacy"))).parent/'*.trk')
    paths   = trkpath, utpath("big_grlegacy")
    track   = data.Track(path = paths)
    keys    = {0, 10, 12, 13, 14, 16, 17, 18, 1, 21, 22, 23,
               24, 25, 26, 27, 28, 29, 2, 34, 35, 37, 3, 4, 6, 7}
    assert set(track.beads.keys()) == keys

def test_scancgr():
    "tests LegacyGRFilesIO.scancgr"
    assert LegacyGRFilesIO.scan("dummy", "dummy") == ((), (), ())

    directory        = Path(cast(str, utpath(None)))
    pairs, grs, trks = LegacyGRFilesIO.scan(directory, directory)
    assert (pairs, grs) == ((), ())
    assert sorted(trks) == sorted(Path(directory).glob("*.trk"))

    pairs, grs, trks = LegacyGRFilesIO.scan(directory, directory, cgrdir = 'CTGT_selection')
    assert len(grs) == 0
    assert pairs    == ((directory/'test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.trk',
                         directory/'CTGT_selection'),)
    assert len(trks) == len(tuple(Path(directory).glob("*.trk"))) - len(pairs)

def test_allleaves():
    'tests pairing of track files and gr-files in the absence of cgr'
    trkpath    = str(Path(cast(str, utpath("big_legacy"))).parent/'*.trk')
    print(trkpath)
    grpath     =  str(Path(cast(str, utpath("big_grlegacy")))/'*.gr')
    print(grpath)
    good,_1,_2 = LegacyGRFilesIO.scan(trkpath,
                                      grpath,
                                      cgrdir="",
                                      allleaves = True)
    assert len(good)==1
    trks = [str(path[0]) for path in good]
    assert utpath("big_legacy") in trks

def test_track_state():
    "test track state"
    trk   = data.Track(path = utpath("small_legacy"), axis = 'Y')
    trk.load()
    state = trk.__getstate__()
    assert state.get('axis', None) == 'Y'
    assert 'phases' in state
    assert 'path'   in state
    assert 'secondaries' not in state
    assert 'data'        not in state

    trk   = data.Track(data = {1: np.arange(5)}, secondaries = {'sec': np.arange(5)})
    trk.load()
    state = trk.__getstate__()
    assert 'secondaries' in state
    assert 'data'        in state

def test_trktopk():
    "tests conversion to pk"
    trk   = data.Track(path = utpath("big_legacy"))
    fname = tempfile.mktemp()+".pk"

    new   = savetrack(fname, trk)
    for key, val in trk._data.items():
        assert new._data[key] is val

    assert new.fov is trk.fov
    assert str(new._path) == fname
    assert new.framerate == trk.framerate
    assert new.phases is trk.phases

    trk = data.Track(path = fname)
    trk.data # pylint: disable=pointless-statement
    for key, val in trk._data.items():
        assert_equal(new._data[key], val)
    assert new.framerate == trk.framerate
    assert_equal(new.phases, trk.phases)

    new = cast(FoV, new.fov)
    fov = cast(FoV, trk.fov)
    # pylint: disable=no-member
    assert_equal(new.image, fov.image)
    assert list(new.dim) == list(fov.dim)
    for i, j in new.beads.items():
        assert list(j.position) == list(fov.beads[i].position)
        assert_equal(j.image, fov.beads[i].image)

    fname = tempfile.mktemp()
    trk = TracksDict()
    trk['i'] = utpath("big_legacy")
    new      = savetrack(fname, trk)

    assert list(new.keys()) == ['i']
    assert new['i'].path == (Path(fname)/"i").with_suffix(".pk")
    assert (Path(fname)/"i").with_suffix(".pk").exists()

def test_io_recognition():
    "tests that the right IO class recognizes its paths"
    get   = lambda i: str(utpath(i))
    files = dict(pickles = ((get("100bp_4mer/ref.pk"),), get("100bp_4mer/ref.pk"),),
                 tracks  = ((get("small_legacy"),), get("small_legacy"),),
                 grs     = ((get("big_legacy"), get("CTGT_selection")),
                            (get("big_legacy"), get("CTGT_selection")+"/Z(t)bd0track10.gr")),
                 none    = (get("CTGT_selection"),
                            get("CTGT_selection")+"/Z(t)bd0track10.gr",
                            (get("CTGT_selection")+"/Z(t)bd0track10.gr"),))

    types = dict(pickles = PickleIO,
                 tracks  = LegacyTrackIO,
                 grs     = LegacyGRFilesIO)
    for tpename, tpe  in types.items():
        for fname, paths in files.items():
            for path in cast(Iterable, paths):
                assert (tpe.check(path) is None) is (tpename != fname)

def test_selectcycles():
    'test whether two Track stack properly'
    trk = Track(path = utpath("big_legacy"))

    other = selectcycles(trk, range(5))
    assert other.ncycles == 5
    assert set(other.beads.keys()) == set(trk.beads.keys())
    assert_allclose(other.phases, trk.phases[:5,:]-trk.phases[0,0])
    assert_allclose(other.secondaries.seconds,
                    trk.secondaries.seconds[:trk.phases[5,0]-trk.phases[0,0]])

    other = selectcycles(trk, [2, 4, 10])
    assert other.ncycles == 3
    assert set(other.beads.keys()) == set(trk.beads.keys())
    assert_allclose(other.phases[0,:], trk.phases[2,:]-trk.phases[2,0])

    other = selectcycles(trk, slice(None, None, 2))
    assert other.ncycles == trk.ncycles//2
    assert set(other.beads.keys()) == set(trk.beads.keys())
    assert_allclose(other.phases[0,:], trk.phases[0,:]-trk.phases[0,0])

def test_concatenate():
    'test whether two Track stack properly'
    trk1 = Track(path = utpath("small_legacy"))
    trk2 = dropbeads(Track(path = utpath("small_legacy")),0)
    size1, size2 = [next(iter(x.data.values())).size for x  in (trk1, trk2)]
    trk  = concatenatetracks(trk1, trk2)

    assert set(trk.data.keys())==(set(trk1.data.keys())|set(trk2.data.keys()))
    assert all((trk.secondaries.seconds[1:]-trk.secondaries.seconds[:-1])==1)
    assert all(np.isnan(trk.data[0][-size2:]))
    assert all(~np.isnan(trk.data[0][:size1]))

    assert_allclose(trk.phases[:len(trk1.phases)],trk1.phases)
    assert_allclose(trk.phases[len(trk1.phases):],
                    trk2.phases+trk1.secondaries.seconds[-1]-trk2.secondaries.seconds[0]+1)

def test_clone():
    'test whether two Track stack properly'
    # pylint: disable=protected-access
    trk1 = Track(path = utpath("small_legacy"))
    trk2 = clone(trk1)
    assert not trk1.isloaded
    assert not trk2.isloaded

    trk1.load()
    trk2 = clone(trk1)
    assert trk1.isloaded
    assert trk2.isloaded
    assert trk1._data is not trk2._data
    assert trk1._secondaries is not trk2._secondaries
    assert trk1._fov is not trk2._fov
    assert all(i is j for i, j in zip(trk1.data.values(), trk2.data.values()))
    assert all(i is j for i, j in zip(trk1._secondaries.values(), trk2._secondaries.values()))
    assert trk1.fov.image is trk2.fov.image

if __name__ == '__main__':
    test_clone()
