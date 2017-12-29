#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for detection of peaks
will be expanded to include different methods
"""
import numpy as np
from numpy.testing import assert_allclose
import scipy.stats as stats
from peakfinding.histogram import ByEM

EMFITTER = ByEM()

def test_byemscore():
    'tests the score method'
    data   = np.array([[0,0],[10,0],[0,1]])
    params = [[(0,1),(0,1)],[(10,0.1),(0,2)],[(5,10),(0,1)],[(0,10),(0.5,1)]]
    score  = EMFITTER.score(data,params)
    assert_allclose(score,np.array([[0.3989,0,0.1468],
                                    [0,1.995,0],
                                    [0.0352,0.0352,0.0129],
                                    [0,0,0.0242]]),
                    rtol=1e-2,
                    atol=1e-2)

    # add test for (x,y,z,t)
    data   = np.array([[0,0,0,1],[-1,0,0,1],[1,0,0,1],[0,1,0,1],[1,0,-1,1]])

    params = [[(np.array(3*[0]),np.diag(3*[1])),(0,1)],
              [(np.arange(3)+1,np.diag(3*[10])),(4,10)],
              [(np.array([10,-20,30]),np.diag(3*[.1])),(0,0.1)]]
    score  = EMFITTER.score(data,params)
    assert_allclose((2*np.pi)**(3/2)*\
                    np.array([[0.023358,0.01416735,0.01416735,0.01416735,0.00859293],
                              [0.,0.,0.,0.,0.],
                              [0.,0.,0.,0.,0.]]),score,rtol=1e-5)

    # to add more tests
    #pdf = lambda d,p: norm(loc=p[0],scale=p[4]).pdf(d[0])*norm(loc=p[1],scale=p[5]).pdf(d[1])
    #* norm(loc=p[2],scale=p[6]).pdf(d[2])
    #* expon(loc=p[3],scale=p[7]).pdf(d[3])

def test_assign():
    'check that events are correctly assigned'
    data   = np.array([[0,0],[10,0],[0,1]])
    params = np.array([[(0,1),(0,1)],[(10,1),(0,1)],[(0,1),(1,1)]])
    score  = EMFITTER.score(data,params)
    assert {0:(0,),1:(1,),2:(2,)}==EMFITTER.assign(score)
    score  = EMFITTER.score(data,params[[1,2,0]])
    assert {0:(1,),1:(2,),2:(0,)}==EMFITTER.assign(score)

def test_byemstep():
    'test the expectation and maximization step of ByEM'
    rstate=np.random.RandomState(2)
    data = np.vstack([np.hstack([stats.norm(loc=i,scale=0.1).rvs((1000,1),random_state=rstate), # pylint: disable=unused-variable
                                 stats.expon(loc=0,scale=0.1).rvs((1000,1),random_state=rstate)])
                      for i in range(0,10,2)])
    byem=ByEM(emiter=1) # pylint: disable=unused-variable
    # byem.fit(data,5)
    # [[(array([-0.01037411]), array(0.010754432724043382)),
    #   (0.0, 0.088473963060729632)],
    #  [(array([ 5.99171057]), array(0.009344976709039427)),
    #   (0.0, 0.071020222705922273)],
    #  [(array([ 1.98797809]), array(0.008596847258001587)),
    #   (0.0, 0.099100349275130326)],
    #  [(array([ 7.99110602]), array(0.00906913159811023)),
    #   (0.0, 0.098698632507821488)],
    #  [(array([ 4.01190038]), array(0.00950468262348866)),
    #   (0.0, 0.098265426016101332)]])

    # for x,y,z and t
    rstate=np.random.RandomState(2)
    # ...
