#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member
"Tests interval detection"
from   typing              import cast
import pickle
from   tests.testutils     import integrationmark

@integrationmark
def test_track(scriptingcleaner):
    "test scripting enhanced track"
    from scripting             import Track, Tasks, localcontext #pylint: disable=no-name-in-module
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
def test_confusion(scriptingcleaner):
    "test the confusion matrix"
    from scripting             import Track #pylint: disable=no-name-in-module
    from scripting.confusion   import ConfusionMatrix, LNAHairpin
    from tests.testingcore     import path as utpath
    peaks = pickle.load(open(cast(str, utpath("hp6jan2018.peaks")), "rb"))
    peaks = peaks[peaks.track != 'ref']
    cnf   = ConfusionMatrix(oligos  = peaks.track.unique(),
                            seq     = LNAHairpin(path = utpath("hp6.fasta")))
    det   = cnf.detection(peaks)
    conf  = cnf.confusion(det)
    return det, conf

if __name__ == '__main__':
    test_track()
