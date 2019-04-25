#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member,unused-argument
# pylint: disable=unused-argument,unused-import,no-name-in-module
"Tests interval detection"
from   typing              import cast
import pickle
from   tests.testutils     import integrationmark

@integrationmark
def test_track(scriptingcleaner):
    "test scripting enhanced track"
    from scripting             import Track, Tasks, localcontext, Task
    from data                  import Cycles, Beads
    from eventdetection.data   import Events
    from peakfinding.processor import PeaksDict
    from tests.testingcore     import path as utpath

    track = Track(path = utpath("big_legacy"))
    assert track.path == utpath("big_legacy")

    assert set(track.data.keys()) == set(list(range(0,39)))
    for i, j in [
            ('cleanbeads',  Beads),
            ('cleancycles', Cycles),
            ('events',      Events),
            ('peaks',       PeaksDict)
    ]:
        itm = getattr(track, i)
        assert isinstance(itm, j)
        assert all(isinstance(k, Task) for k in itm.tasklist)
    assert track.cleaned is False

    assert ([Tasks(i) for i in Tasks.defaulttasklist(None, Tasks.clipping, False)]
            == [Tasks.cleaning, Tasks.alignment, Tasks.clipping])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.clipping)]
            == [Tasks.cleaning, Tasks.alignment, Tasks.clipping])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, ...)]
            == [Tasks.cleaning, Tasks.alignment, Tasks.clipping, Tasks.eventdetection,
                Tasks.peakselector, Tasks.fittohairpin])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(None, Tasks.alignment, True)]
            == [Tasks.alignment])
    track.cleaned = True
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
            == [Tasks.alignment])
    with localcontext(scripting = {'alignalways': False}):
        assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
                == [])

    assert track.tasks.subtraction is None
    track.tasks.subtraction = 1 # type: ignore
    assert set(track.tasks.subtraction.beads) == {1}
    track.tasks.subtraction = 1,2
    assert set(track.tasks.subtraction.beads) == {1,2}
    track.cleaned = False
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
            == [Tasks.subtraction, Tasks.cleaning, Tasks.alignment])

    assert track.op[:,:5].ncycles == 5
    assert set(track.op[[1,2]].beads.keys()) == {1,2}

@integrationmark
def test_trackconfig(scriptingcleaner):
    "test scripting enhanced track"
    from scripting             import Track, Tasks, localcontext
    from data                  import Cycles
    from eventdetection.data   import Events
    from peakfinding.processor import PeaksDict
    from tests.testingcore     import path as utpath

    track = Track(path = utpath("big_legacy"))
    assert track.path == utpath("big_legacy")

    assert set(track.data.keys()) == set(list(range(0,39)))
    assert isinstance(track.cleancycles,    Cycles)
    assert isinstance(track.measures,       Cycles)
    assert isinstance(track.events,         Events)
    assert isinstance(track.peaks,          PeaksDict)

@integrationmark
def test_confusion(scriptingcleaner):
    "test the confusion matrix"
    from scripting             import Track
    from scripting.confusion   import ConfusionMatrix, LNAHairpin
    from tests.testingcore     import path as utpath
    peaks = pickle.load(open(cast(str, utpath("hp6jan2018.peaks")), "rb"))
    peaks = peaks[peaks.track != 'ref']
    cnf   = ConfusionMatrix(oligos  = peaks.track.unique(),
                            seq     = LNAHairpin(path = utpath("hp6.fasta")))
    det   = cnf.detection(peaks)
    conf  = cnf.confusion(det)
    return det, conf

@integrationmark
def test_muwells(scriptingcleaner):
    "test µwells"
    from scripting          import Track
    from tests.testingcore  import path as utpath
    trackfile = utpath("muwells/W6N46_HPB20190107_W2_OR134689_cycle_1.9-2.10_TC10m.trk")
    liafile   = utpath("muwells/W6N46_HPB20190107_OR134689_cycle_1.9-2.10_TC10m.txt")
    track     = Track(path= (trackfile, liafile))
    assert set(track.tasks.tasks.keys()) == set()
    other     = track.op.rescaletobead(0)
    assert track is not other
    assert set(other.tasks.tasks.keys()) == {
        'cleaning', 'alignment', 'eventdetection', 'peakselector'
    }

if __name__ == '__main__':
    test_muwells(None)
