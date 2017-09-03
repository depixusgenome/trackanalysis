#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
import numpy as np
from   numpy.testing            import assert_equal, assert_allclose

from testingcore                import path as utpath
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from cleaning.processor         import DataCleaning, DataCleaningTask, DataCleaningProcessor
from cleaning.beadsubtraction   import BeadSubtractionTask, BeadSubtractionProcessor
from simulator                  import randtrack, setseed
from control.taskcontrol        import create
from data                       import Beads, Track

def test_constantvalues():
    "test constant values"
    setseed(0)
    bead = np.random.normal(.1, 3e-3, 50)

    bead[:3]    = 100.
    bead[10:13] = 100.
    bead[20:30] = 100.
    bead[40:42] = 100.
    bead[-3:]   = 100.

    fin                  =  np.abs(bead-100.) < 1e-5
    fin[[0,10,20,40,41,-3]] = False

    DataCleaning().constant(bead)

    assert_equal(np.isnan(bead), fin)

    bead[:3]    = 100.
    bead[10:13] = 100.
    bead[20:30] = 100.
    bead[40:42] = 100.
    bead[-3:]   = 100.

    DataCleaning(mindeltarange=5).constant(bead)
    fin[:] = False
    fin[21:30] = True
    assert_equal(np.isnan(bead), fin)

def test_cleaning_base():
    "test cleaning"
    setseed(0)
    cycs = np.random.normal(.1, 3e-3, 1000).reshape(10,-1)
    cycs[0,:]      = np.random.normal(1., 4e-2, 100)
    cycs[:,50:]   += .51
    cycs[1,:]      = np.random.normal(.5, 1e-5, 100)
    cycs[2,:]      = np.random.normal(.0, 3e-3, 100)
    cycs[3,:22]    = np.NaN
    cycs[4,3:69:3] += 2.5
    cycs[5,:22]    += 5.7

    tsk = DataCleaning()
    assert set(tsk.hfsigma(cycs).min) == set([1])
    assert set(tsk.hfsigma(cycs).max) == set([0, 4])
    assert set(tsk.extent(cycs).min) == set([1, 2])
    assert set(tsk.extent(cycs).max) == set([])
    assert set(tsk.population(cycs).min) == set([3])
    tsk.aberrant(cycs.ravel())
    assert set(tsk.population(cycs).min) == set([3,4,5])
    assert set(tsk.population(cycs).max) == set([])

def test_subtract():
    "tests subtractions"
    assert_allclose(BeadSubtractionTask()([np.arange(5)]),   np.arange(5))
    assert_allclose(BeadSubtractionTask()([np.arange(5)]*5), np.arange(5))
    assert_allclose(BeadSubtractionTask()([np.arange(5), np.ones(5)]),
                    np.arange(5)*.5+.5)

    assert_allclose(BeadSubtractionTask()([np.arange(6), np.ones(5)]),
                    list(np.arange(5)*.5+.5)+[5])

    tmp = Beads(data = {0: np.arange(5), 1: np.ones(5),
                        2: np.zeros(5),  3: np.arange(5)*1.})
    cache = {}
    frame = BeadSubtractionProcessor.apply(tmp, cache, beads = [0, 1])
    assert set(frame.keys()) == {2, 3}
    assert_allclose(frame[2], -.5*np.arange(5)-.5)
    assert_allclose(cache[None],  .5*np.arange(5)+.5)

    ca0 = cache[None]
    res = frame[3]
    assert res is frame.data[3] # pylint: disable=unsubscriptable-object
    assert ca0 is cache[None]

def test_processor():
    "test processor"
    # pylint: disable=expression-not-assigned
    cache = {}
    trk   = randtrack().beads
    DataCleaningProcessor.apply(trk, cache)[0]
    assert len(list(cache.keys())) == 1
    assert isinstance(next(iter(cache.keys())), Track)

    trkcache = next(iter(cache.values()))
    assert list(trkcache) == [0]
    tmp = trkcache[0]
    DataCleaningProcessor.apply(trk, cache)[0]
    assert tmp is next(iter(cache.values()))[0]

def test_processor2():
    "test processor"
    proc  = create(utpath("big_all"), DataCleaningTask())
    _     = next(iter(proc.run()))[0]
    cache = proc.data[1].cache()
    assert len(cache) == 1
    cache = next(iter(cache.values()))
    assert len(cache) == 1
    assert 0 in cache

def test_view(bokehaction):
    "test the view"
    with bokehaction.launch('cleaning.view.CleaningView', 'app.toolbar') as server:
        server.ctrl.observe("rendered", lambda *_1, **_2: server.wait())
        server.load('big_legacy', andstop = False)

        assert server.task(DataCleaningTask).maxhfsigma != 0.002
        server.change('Cleaning:Filter', 'maxhfsigma', 0.002)
        server.wait()
        assert server.widget['Cleaning:Filter'].maxhfsigma == 0.002
        assert server.task(DataCleaningTask).maxhfsigma == 0.002

if __name__ == '__main__':
    test_cleaning_base()
