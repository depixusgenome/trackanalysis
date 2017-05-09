#!/usr/bin/env python3
# -*- coding: utf-8 -*-

u''' scoring functions for assembly
'''

import scipy.stats as stats
from numpy.testing import assert_allclose
from numpy import array
from pytest import approx # pylint: disable=no-name-in-module
from assemble import data
from assemble import scores

DIST1 = stats.norm(loc=1.0,scale=0.5)
OLI1 = data.OligoPeak(dist=DIST1)

DIST2 = stats.norm(loc=2.0,scale=0.5)
OLI2 = data.OligoPeak(dist=DIST2)

DIST3 = stats.norm(loc=3.0,scale=0.5)

def test_PDFCost():
    u'tests'
    okp = scores.PDFCost(perm=(0,1),dists=[DIST1,DIST2])
    assert okp([1,2])==approx(-0.636619772368,abs=1e-5)
    assert okp([0.5,2])==approx(-0.38612941052,abs=1e-5)
    assert okp([1,2.5])==approx(-0.38612941052,abs=1e-5)

def test_OptiDistPerm():
    u'tests'
    epsi = 0.01
    odp = scores.OptiDistPerm(perm=(0,1),dists=[DIST1,DIST2],__epsi=epsi)
    assert_allclose(odp.run(),array([1,2]),rtol=1e-4,atol=1e-4)
    assert_allclose(odp.run(xinit=[1,2]),array([1,2]),rtol=1e-4,atol=1e-4)
    assert_allclose(odp.run(xinit=[1.2,2.2]),array([1,2]),rtol=1e-4,atol=1e-4)
    assert_allclose(odp.run(xinit=[0.8,2.2]),array([1,2]),rtol=1e-4,atol=1e-4)
    assert_allclose(odp.run(xinit=[0.8,1.8]),array([1,2]),rtol=1e-4,atol=1e-4)

    odp = scores.OptiDistPerm(perm=(1,0),dists=[DIST1,DIST2],__epsi=epsi)
    assert_allclose(odp.run(),array([1.4999,1.5001]),rtol=1e-4,atol=1e-4)
    assert_allclose(odp.run(xinit=[1,2]),array([1.4999,1.5001]),rtol=1e-4,atol=1e-4)
    assert_allclose(odp.run(xinit=[2,1]),array([1.4999,1.5001]),rtol=1e-4,atol=1e-4)

    # should be 1,2,3
    odp = scores.OptiDistPerm(perm=(0,1,2),dists=[DIST1,DIST2,DIST3],__epsi=epsi)
    assert_allclose(odp.run(),array([1.,2.,3.]),rtol=1e-4,atol=1e-4)

    odp = scores.OptiDistPerm(perm=(0,2,1),dists=[DIST1,DIST2,DIST3],__epsi=epsi)
    assert_allclose(odp.run(),array([1.,2.4999,2.5000]),rtol=1e-4,atol=1e-4)

    odp = scores.OptiDistPerm(perm=(1,0,2),dists=[DIST1,DIST2,DIST3],__epsi=epsi)
    assert_allclose(odp.run(),array([1.4999,1.5000,3.0]),rtol=1e-4,atol=1e-4)

    odp = scores.OptiDistPerm(perm=(1,2,0),dists=[DIST1,DIST2,DIST3],__epsi=epsi)
    assert_allclose(odp.run(),array([1.9998,1.9999,2.000]),rtol=1e-4,atol=1e-4)

def test_OptiKPerm():
    u'tests'
    # no permutation
    kperm=[OLI1,OLI2]
    okp = scores.OptiKPerm(kperm=kperm)
    assert_allclose(okp.pstate,array([1.,2.]),rtol=1e-4,atol=1e-4)
    assert okp.cost()==approx(-0.63662,abs=1e-5)

    # permuting two elements
    kperm=[OLI2,OLI1]
    okp = scores.OptiKPerm(kperm=kperm)
    assert_allclose(okp.pstate,array([1.4999,1.5000]),rtol=1e-4,atol=1e-4)
    assert okp.cost()==approx(-0.23415,abs=1e-5)

    # permuting 3-elements...
