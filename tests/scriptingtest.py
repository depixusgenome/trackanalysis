#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member
"Tests interval detection"
import sys
sys.modules['ACCEPT_SCRIPTING'] = True
from scripting              import Track, Tasks, localcontext
import numpy                as np
from data                   import Cycles
from data.track             import dropbeads
from eventdetection.data    import Events
from peakfinding.processor  import PeaksDict
from testingcore            import path as utpath

def test_track():
    "test scripting enhanced track"
    assert 'scripting.jupyter' not in sys.modules

    track = Track(path = utpath("big_legacy"))
    assert track.path == (utpath("big_legacy"),)

    track = Track(utpath("big_legacy"))
    assert track.path == (utpath("big_legacy"),)
    assert set(track.data.keys()) == {'t', 'zmag'} | set(list(range(0,39)))
    assert isinstance(track.cleancycles,    Cycles)
    assert isinstance(track.measures,       Cycles)
    assert isinstance(track.events,         Events)
    assert isinstance(track.peaks,          PeaksDict)
    assert isinstance(track.tasks.config(), dict)
    assert not track.tasks.config()
    assert track.cleaned is False

    assert ([Tasks(i) for i in Tasks.defaulttasklist(None, Tasks.alignment, False)]
            == [Tasks.cleaning, Tasks.alignment])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
            == [Tasks.cleaning, Tasks.alignment])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, ...)]
            == [Tasks.cleaning, Tasks.alignment, Tasks.eventdetection,
                Tasks.peakselector, Tasks.fittohairpin])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(None, Tasks.alignment, True)]
            == [Tasks.alignment])
    track.cleaned = True
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
            == [Tasks.alignment])
    with localcontext().update(config = {'tasks.scripting.alignment.always': False}):
        assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
                == [])

    assert track.tasks.subtraction == ()
    track.tasks.subtraction = 1
    assert track.tasks.subtraction == (1,)
    track.tasks.subtraction = 1,2
    assert track.tasks.subtraction == (1,2)
    track.cleaned = False
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
            == [Tasks.subtraction, Tasks.cleaning, Tasks.alignment])

def test_concatenate():
    'test whether two Track stack properly'
    trk1 = Track(path = utpath("small_legacy"))
    trk2 = dropbeads(Track(path = utpath("small_legacy")),0)
    size1, size2 = trk1.data["t"].size, trk2.data["t"].size
    trk  = trk1.concatenate(trk2)

    assert set(trk.data.keys())==(set(trk1.data.keys())|set(trk2.data.keys()))
    assert all((trk.data["t"][1:]-trk.data["t"][:-1])==1)
    assert all(np.isnan(trk.data[0][-size2:]))
    assert all(~np.isnan(trk.data[0][:size1]))

    assert trk.phases[:len(trk1)]==trk1.phases
    assert trk.phases[len(trk1):]==trk2.phases+trk1.data["t"][-1]-trk2.data["t"][-1]+1
