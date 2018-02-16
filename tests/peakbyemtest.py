#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for detection of peaks
will be expanded to include different methods
"""
import pickle

import numpy as np
from numpy.testing       import assert_allclose

from peakfinding.groupby import ByEM
from testingcore         import path as utfilepath

EMFITTER = ByEM()
DATA     = pickle.load(open(utfilepath('smallemdata'),"rb"))

def test_ztscore():
    'tests the score method'
    data   = np.array([[0,0],[10,0],[0,1]])
    params = np.array([[0,1,0,1],[10.,0.1**2,0,2],[5,100,0,1],[0,100,0.5,1]])
    score  = EMFITTER.score(data,params)
    assert_allclose(score,np.array([[0.3989,0,0.1468],
                                    [0,1.995,0],
                                    [0.0352,0.0352,0.0129],
                                    [0,0,0.0242]]),
                    rtol=1e-2,
                    atol=1e-2)

def test_xyztscore():
    'add test for (x,y,z,t)'
    data   = np.array([[0,0,0,1],[-1,0,0,1],[1,0,0,1],[0,1,0,1],[1,0,-1,1]])

    params = np.array([[0.,1,0,1,0,1,0,1],[1,10.,2,10.,3,10.,4,10],[10,0.1,-20,0.1,30,0.1,0,0.1]])
    score  = EMFITTER.score(data,params)
    floaterr=1e-8
    assert_allclose(floaterr+np.array([[0.023358,0.01416735,0.01416735,0.01416735,0.00859293],
                                       [0.,0.,0.,0.,0.],
                                       [0.,0.,0.,0.,0.]]),score,rtol=1e-5)

    # to add more tests
    #pdf = lambda d,p: norm(loc=p[0],scale=p[4]).pdf(d[0])*norm(loc=p[1],scale=p[5]).pdf(d[1])
    #* norm(loc=p[2],scale=p[6]).pdf(d[2])
    #* expon(loc=p[3],scale=p[7]).pdf(d[3])

def test_assign():
    'check that events are correctly assigned'
    data   = np.array([[0,0],[10,0],[0,1]])
    params = np.array([[0,1,0,1],[10,1,0,1],[0,1,1,1]])
    score  = EMFITTER.score(data,params)
    assert {0:(0,),1:(1,),2:(2,)}==EMFITTER.assign(score)
    score  = EMFITTER.score(data,params[[1,2,0]])
    assert {0:(1,),1:(2,),2:(0,)}==EMFITTER.assign(score)

def test_emstep():
    'tests emstep on 2 distinct peaks'
    params = np.array([[0,10,0.,1.5e+01],
                       [0,11,0.,8.8e+01]])
    rates           = 0.5*np.ones((2,1))
    EMFITTER.emiter = 100
    _,rates,params  = EMFITTER.cfit(DATA,rates,params)
    assert_allclose(params,np.array([[6.099034e-02,1.401e-06,0.,3.75365918e+01],
                                     [7.441417e-02,1.00e-06,0.,1.15579996e+02]]),
                    rtol=1e-4)
    # ratio of events assigned to each of the 2 peaks
    assert_allclose(rates,np.array([[0.45054946],
                                    [0.54945054]]))
