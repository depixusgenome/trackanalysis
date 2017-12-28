#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for detection of peaks
will be expanded to include different methods
"""
import numpy as np
from numpy.testing import assert_allclose

from peakfinding.histogram import ByEM

EMFITTER = ByEM()

def test_byemscore():
    'tests the score method'
    data   = np.array([[0,0],[10,0],[0,1]])
    params = np.array([[0,0,1,1],[10,0,0.1,2],[5,0,10,1],[0,0.5,10,1]])
    score  = EMFITTER.score(data,params)
    assert_allclose(score,np.array([[0.3989,0,0.1468],
                                    [0,1.995,0],
                                    [0.0352,0.0352,0.0129],
                                    [0,0,0.0242]]),
                    rtol=1e-2,
                    atol=1e-2)

    # add test for (x,y,z,t)
    data   = np.array([[0,0,0,1],[-1,0,0,1],[1,0,0,1],[0,1,0,1],[1,0,-1,1]])
    params = np.array([[0,0,0,0,1,1,1,1],
                       [1,2,3,4,10,10,10,10],
                       [10,-20,30,0,0.1,0.1,0.1,0.1]])

    score  = EMFITTER.score(data,params)
    assert_allclose(np.array([[0.023358,0.01416735,0.01416735,0.01416735,0.00859293],
                              [0.,0.,0.,0.,0.],
                              [0.,0.,0.,0.,0.]]),score,rtol=1e-5)

    # to add more tests
    #pdf = lambda d,p: norm(loc=p[0],scale=p[4]).pdf(d[0])*norm(loc=p[1],scale=p[5]).pdf(d[1])
    #* norm(loc=p[2],scale=p[6]).pdf(d[2])
    #* expon(loc=p[3],scale=p[7]).pdf(d[3])

def test_assign():
    'check that events are correctly assigned'
    data   = np.array([[0,0],[10,0],[0,1]])
    params = np.array([[0,0,1,1],[10,0,1,1],[0,1,1,1]])
    score  = EMFITTER.score(data,params)
    assert {0:(0,),1:(1,),2:(2,)}==EMFITTER.assign(score)
    score  = EMFITTER.score(data,params[[1,2,0]])
    assert {0:(1,),1:(2,),2:(0,)}==EMFITTER.assign(score)

def test_byemmaximize():
    'test the maximization step of ByEM'
    pass
