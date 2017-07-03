#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from cleaning.processor import DataCleaning, DataCleaningProcessor
from simulator          import randtrack
import numpy as np

def test_cleaning_base():
    "test cleaning"
    cycs = np.random.normal(.1, 3e-3, 1000).reshape(10,-1)
    cycs[:,50:]   += .41
    cycs[0,:]     += np.random.normal(0., 2e-2, 100)
    cycs[1,:]     += np.random.normal(0., 9e-5, 100)
    cycs[2,:]      = np.random.normal(0., 3e-3, 100)
    cycs[3,:22]    = np.NaN
    cycs[4,3:69:3] += 2.5
    cycs[5,:22]    += 5.2

    tsk = DataCleaning()
    assert set(tsk.hfsigma(cycs).min) == set([0])
    assert set(tsk.hfsigma(cycs).max) == set([1])
    assert set(tsk.extent(cycs).min) == set([2])
    assert set(tsk.extent(cycs).max) == set([])
    assert set(tsk.population(cycs).min) == set([3])
    tsk.aberrant(cycs)
    assert set(tsk.population(cycs).max) == set([3,4,5])

def test_processor():
    "test processor"
    # pylint: disable=expression-not-assigned
    cache = {}
    trk   = randtrack().beads
    DataCleaningProcessor.apply(trk, cache)[0]
    assert list(cache.keys()) == [0]
    tmp = cache[0]
    DataCleaningProcessor.apply(trk, cache)[0]
    assert tmp is cache[0]
