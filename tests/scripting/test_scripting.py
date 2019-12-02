#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,wildcard-import,unused-wildcard-import
# pylint: disable=wrong-import-position,ungrouped-imports,no-member,unused-argument
# pylint: disable=unused-argument,unused-import,no-name-in-module
"Tests interval detection"
from   typing              import cast
import pickle
import sys
from   tests.testutils     import integrationmark

@integrationmark
def test_track(scriptingcleaner):
    "test scripting enhanced track"
    from scripting             import Track, Tasks, localcontext, Task
    from data                  import Cycles, Beads
    from eventdetection.data   import Events
    from peakfinding.processor import PeaksDict
    from taskmodel             import InstrumentType
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
            == [Tasks.undersampling, Tasks.cleaning, Tasks.alignment, Tasks.clipping])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, Tasks.clipping)]
            == [Tasks.undersampling, Tasks.cleaning, Tasks.alignment, Tasks.clipping])
    assert ([Tasks(i) for i in Tasks.defaulttasklist(track, ...)]
            == [Tasks.undersampling, Tasks.cleaning, Tasks.alignment, Tasks.clipping, Tasks.eventdetection,
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
            == [Tasks.undersampling, Tasks.subtraction, Tasks.cleaning, Tasks.alignment])

    assert track.op[:,:5].ncycles == 5
    assert set(track.op[[1,2]].beads.keys()) == {1,2}

    assert InstrumentType(utpath("big_legacy")) == InstrumentType.picotwist
    assert InstrumentType(utpath("sdi_track.pk")) == InstrumentType.sdi
    assert Tasks.peakselector(instrument = utpath("big_legacy")).rawfactor == 2.
    assert track.peaks.tasklist[-1].rawfactor == 2.
    assert Tasks.peakselector(instrument = utpath("sdi_track.pk")).rawfactor == 1.
    assert Track(path = utpath("sdi_track.pk")).peaks.tasklist[-1].rawfactor == 1.

@integrationmark
def test_track_dataframe(scriptingcleaner):
    "test scripting enhanced track"
    from scripting import Track, Tasks, localcontext, Task
    from data import Cycles, Beads
    from eventdetection.data import Events
    from peakfinding.processor import PeaksDict
    from tests.testingcore import path as utpath
    from cleaning.processor import DataCleaningTask

    track = Track(path=utpath("small_legacy"))
    assert track.path == utpath("small_legacy")

    raw_df = track.beads.dataframe()
    clean_df = track.apply(..., Tasks.cleaning(maxsaturation=20, maxextent=2)).dataframe()

    assert set(raw_df.columns) == set(clean_df.columns)  # columns should remain the same
    assert hasattr(raw_df, 'tasklist')
    assert hasattr(clean_df, 'tasklist')

    assert len(raw_df.tasklist) == 0
    assert DataCleaningTask in [type(task) for task in clean_df.tasklist]

    assert clean_df.isna().sum().sum() > raw_df.isna().sum().sum()  # cleaned data replaced by NaNs
    assert (clean_df['cycleframe']==1).sum() == track.ncycles  # all cycles should have at least 2 frames

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

@integrationmark
def test_tracksdict_hpfit_dataframe(scriptingcleaner):
    "test that we can launch a fit to hp on a tracksdict"
    from scripting          import TracksDict
    from tests.testingcore  import path as utpath
    import pandas as pd
    tracks = TracksDict()
    tracks['xxx'] = utpath("big_legacy")
    frame = tracks.peaks.dataframe(sequence = utpath("hairpins.fasta"), oligos = '4mer')
    assert isinstance(frame, pd.DataFrame)
    assert len(frame.tasklist) == 1
    assert isinstance(frame.tasklist[0], list)
    assert frame.tasklist[0][-2].oligos == "4mer"
    assert list(frame.oligo.unique()) == ["ctgt"]
    assert frame.shape == (80, 27)
    assert frame.index.names == ['hpin', 'track', 'bead']

    assert 'trackcount' in frame.columns
    assert 'modification' in frame.columns
    assert hasattr(frame, 'tasklist')

def customf(*args,**kwa):
    "custom and picklable function for peaks.dataframe"
    return 2

@integrationmark
def test_tracksdict_custom_dataframe(scriptingcleaner):# 
    "test that we can apply custom function to dataframe"
    from scripting          import TracksDict
    from tests.testingcore  import path as utpath
    import pandas as pd
    tracks = TracksDict()
    tracks['xxx'] = utpath("big_legacy")

    frame = tracks.peaks.dataframe(test = customf, std = 'std')
    assert isinstance(frame, pd.DataFrame)
    assert isinstance(frame.tasklist[0], list)
    assert frame.shape == (285,9)
    assert frame.index.names == ['track', 'bead']

    assert 'test' in frame.columns
    assert 'std' in frame.columns


@integrationmark
def test_tracksdict_cleaning_dataframe(scriptingcleaner):
    "test TracksDict.basedataframe"
    from scripting          import TracksDict
    from tests.testingcore  import path as utpath
    tracks = TracksDict(utpath("100bp_4mer")+"/*.pk")

    dframe = tracks.dataframe(status = True)
    assert 'trackcount' in dframe.columns
    assert 'modification' in dframe.columns
    assert hasattr(dframe, 'tasklist')

    dframe = tracks.dataframe(loadall = True)
    assert 'good' in dframe.columns
    assert 'fixed' in dframe.columns
    assert not all(i is None for i in dframe['good'])
    assert not all(i is None for i in dframe['fixed'])

@integrationmark
def test_tracksdict_ramps_dataframe(scriptingcleaner):
    "test TracksDict.basedataframe"
    from scripting          import TracksDict
    from tests.testingcore  import path as utpath
    tracks = TracksDict(utpath("100bp_4mer")+"/../ramp*.trk")

    dframe = tracks.dataframe(ramps = True)
    assert 'modification' in dframe.columns
    assert hasattr(dframe, 'tasklist')
    assert dframe.tasklist[0][-1].__class__.__name__.startswith("Ramp")

@integrationmark
def test_tracksdict_ramps_beaddata(scriptingcleaner):
    "test TracksDict.basedataframe"
    sys.modules['ACCEPT_SCRIPTING'] = 'jupyter'
    from scripting import TracksDict
    from tests.testingcore import path as utpath
    track = TracksDict(utpath("100bp_4mer")+"/../ramp*.trk")['Hela_mRNA_CIP_4ul_F9']
    data = track.ramp.beaddata(8)
    assert list(data.columns) == ['zmag', 'z', 'phase', 'cycle']
    assert data['zmag'].dropna().shape[0] == track.nframes
    assert data['z'].mean() > 0.01
    assert data.dropna().shape[0] > 0.99*data.shape[0]

@integrationmark
def test_viewer(scriptingcleaner):
    "test TracksDict.basedataframe"
    from scripting import displaytrack, displaytracksdict
    from textwrap import dedent
    vals  = (str(displaytrack())+'\n'+str(displaytracksdict())).strip()
    truth = dedent("""
    Column
        [0] Row
            [0] TextInput(name='Path', value='./**/*.trk', width=600)
            [1] TextInput(name='Match', width=200)
        [1] Select(name='Track', width=850)
        [2] HoloViews(Div)
    Column
        [0] Row
            [0] TextInput(name='Path', value='./**/*.trk', width=600)
            [1] TextInput(name='Match', width=200)
        [1] CrossSelector(name='Track', width=850)
        [2] HoloViews(Div)
    """).strip()
    assert vals == truth


if __name__ == '__main__':
    test_tracksdict_ramps_dataframe(None)
