#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member
"Tests interval detection"
import sys
sys.modules['ACCEPT_SCRIPTING'] = True
from scripting             import Track, Tasks, localcontext #pylint: disable=no-name-in-module
from data                  import Cycles
from eventdetection.data   import Events
from peakfinding.processor import PeaksDict
from testingcore           import path as utpath

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

    assert track.tasks.subtraction is None
    track.tasks.subtraction = 1
    assert set(track.tasks.subtraction.beads) == {1}
    track.tasks.subtraction = 1,2
    assert set(track.tasks.subtraction.beads) == {1,2}
    track.cleaned = False
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.alignment)]
            == [Tasks.subtraction, Tasks.cleaning, Tasks.alignment])

    assert track.op[:,:5].ncycles == 5
    assert set(track.op[[1,2]].beadsonly.keys()) == {1,2}

if __name__ == '__main__':
    test_track()
