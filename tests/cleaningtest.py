#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from cleaning.processor import DataCleaning, DataCleaningProcessor
from simulator          import randtrack, setseed
import numpy as np

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
    cycs[5,:22]    += 5.2

    tsk = DataCleaning()
    assert set(tsk.hfsigma(cycs).min) == set([1])
    assert set(tsk.hfsigma(cycs).max) == set([0, 4])
    assert set(tsk.extent(cycs).min) == set([1, 2])
    assert set(tsk.extent(cycs).max) == set([])
    assert set(tsk.population(cycs).min) == set([3])
    tsk.aberrant(cycs.ravel())
    assert set(tsk.population(cycs).min) == set([3,4,5])
    assert set(tsk.population(cycs).max) == set([])

def test_processor():
    "test processor"
    # pylint: disable=expression-not-assigned
    cache = {}
    trk   = randtrack().beads
    DataCleaningProcessor.apply(trk, cache)[0]
    assert list(cache.keys()) == [((None,), 0)]
    tmp = cache[(None,), 0]
    DataCleaningProcessor.apply(trk, cache)[0]
    assert tmp is cache[(None,), 0]

def test_view(bokehaction):
    "test the view"
    with bokehaction.serve('cleaning.view.CleaningView', 'app.BeadToolbar') as server:
        server.ctrl.observe("rendered", lambda *_1, **_2: server.wait())
        server.load('big_legacy', andstop = False)

if __name__ == '__main__':
    test_view(bokehaction(None))
