#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"testing peakcalling"
# pylint: disable=import-error,no-name-in-module
import numpy as np
from numpy.testing          import assert_allclose, assert_equal
from pytest                 import approx

from control.taskcontrol    import create
from simulator.processor    import ByPeaksEventSimulatorTask
from peakcalling            import cost, match
from peakcalling.processor  import (BeadsByHairpinProcessor, BeadsByHairpinTask,
                                    PeakIdentifier, HairpinDistance,
                                    DistanceConstraint)

def test_cost_value():
    u"Tests peakcalling.cost.compute"
    bead1 = np.arange(10)
    bead2 = np.arange(10)+10.
    bead3 = np.arange(10)*.5+5.
    truth = approx((0., 0., 0.))
    for sym in (False, True):
        assert cost.compute(bead1, bead1, sym, .01, 1., 0.)   == truth
        assert cost.compute(bead1, bead2, sym, .01, 1., -10.) == truth
        assert cost.compute(bead1, bead3, sym, .01, 2., -10.) == truth

        assert cost.compute(bead1, bead3, sym, .01, 1.99, -10.)[0] > 0.
        assert cost.compute(bead1, bead3, sym, .01, 1.99, -10.)[1] < 0.

        assert cost.compute(bead1, bead3, sym, .01, 2.01, -10.)[0] > 0.
        assert cost.compute(bead1, bead3, sym, .01, 2.01, -10.)[1] > 0.

        assert cost.compute(bead1, bead3, sym, .01, 2., -10.1)[0]  > 0.
        assert cost.compute(bead1, bead3, sym, .01, 2., -10.1)[2]  < 0.

        assert cost.compute(bead1, bead3, sym, .01, 2., -9.9)[0]   > 0.
        assert cost.compute(bead1, bead3, sym, .01, 2., -9.9)[2]   > 0.

def test_cost_optimize():
    u"Tests peakcalling.cost.optimize"
    bead1 = np.array([1, 5, 10], dtype = np.float32)
    bead2 = (bead1-.2)/.9
    val   = cost.optimize(bead1, bead2, False, 1., min_bias = -.5, max_bias = .5)
    assert val == approx((0., .9, .2), abs = 1e-5)

def test_match():
    u"Tests peakcalling.match.compute"
    bead1 = np.array([1, 5, 10, 32], dtype = np.float32)
    assert (match.compute(bead1, bead1-1.)-[[0,0], [1,1], [2, 2], [3, 3]]).sum() == 0
    assert (match.compute(bead1, [.8, 6., 35.])-[[0,0], [1,1], [3, 2]]).sum() == 0
    assert (match.compute(bead1, [.8, 35., 37.])-[[0,0], [3, 1]]).sum() == 0
    assert (match.compute(bead1, [-100., 5., 37.])-[[1,1], [3, 2]]).sum() == 0

def test_onehairpincost():
    u"tests hairpin cost method"
    truth = np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4
    bead  = (truth*1.03+1.)*8.8e-4
    res   = HairpinDistance(peaks = truth)(bead[:-1])
    assert_allclose((bead-res[2])*res[1], truth, rtol = 1e-4, atol = 1e-2)

def test_onehairpinid():
    u"tests haipin id method"
    truth = np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4
    bead  = np.array([0., 0.01, .1, .2, .5, 1.], dtype = 'f4') - .88e-4
    res   = PeakIdentifier(peaks = truth)(bead, 1./8.8e-4, 10.)
    assert_allclose(res['zvalue'], bead)
    assert_allclose(res['key'], np.insert(np.int32(truth[:-1]+.1), 1, np.iinfo('i4').min))

def test_hairpincost():
    u"tests hairpin cost method"
    truth = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4,
             np.array([0., .1,     .5, 1.2, 1.5], dtype = 'f4')/8.8e-4]

    beads = [(100, np.array([0., 0.01, .1, .2, .5, 1.], dtype = 'f4') - .88e-4),
             (101, (truth[1][:-1]*.97-1) *8.8e-4),
             (110, np.empty((0,), dtype = 'f4'))]

    hpins   = {'hp100': HairpinDistance(peaks = truth[0]),
               'hp101': HairpinDistance(peaks = truth[1])}
    ids     = {'hp100': PeakIdentifier(peaks = truth[0]),
               'hp101': PeakIdentifier(peaks = truth[1])}
    results = dict(BeadsByHairpinProcessor.compute(hpins, {}, ids, beads))
    assert len(results) == 3
    assert len(results['hp100']) == 1
    assert len(results['hp101']) == 1
    assert len(results[None])    == 1
    assert results['hp100'][0].key == 100
    assert results['hp101'][0].key == 101
    assert_equal(results['hp100'][0].peaks['key'],
                 np.insert(np.int32(truth[0][:-1]+.1), 1, np.iinfo('i4').min))
    assert_equal(results['hp101'][0].peaks['key'], np.int32(truth[1][:-1]+.1))
    assert results[None][0].key    == 110

def test_constrainedhairpincost():
    u"tests hairpin cost method with constraints"
    truth = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4,
             np.array([0., .1,     .5, 1.2, 1.5], dtype = 'f4')/8.8e-4]

    beads = [(100, (truth[0][:-1]*1.03+1.)*8.8e-4),
             (101, (truth[1][:-1]*.97-1) *8.8e-4),
             (110, np.empty((0,), dtype = 'f4'))]

    hpins   = {'hp100': HairpinDistance(peaks = truth[0]),
               'hp101': HairpinDistance(peaks = truth[1])}
    cstrs   = dict.fromkeys((100, 110), DistanceConstraint('hp101', {}))

    results = dict(BeadsByHairpinProcessor.compute(hpins, cstrs, {}, beads))
    assert len(results) == 1
    assert len(results['hp101']) == 3

def test_control():
    u"tests BeadsByHairpinTask using the controller"
    peaks = np.array([0.,  .1, .5, .6, 1.], dtype = 'f4')
    truth = [np.array([0., .1, .5, 1.,       1.5], dtype = 'f4')/8.8e-4,
             np.array([0.,     .5,      1.2, 1.5], dtype = 'f4')/8.8e-4]
    hpins = {'hp100': HairpinDistance(peaks = truth[0]),
             'hp101': HairpinDistance(peaks = truth[1])}
    pair  = create((ByPeaksEventSimulatorTask(peaks    = peaks,
                                              brownian = .01,
                                              stretch  = None,
                                              bias     = None,
                                              rates    = None,
                                              nbeads   = 1,
                                              ncycles  = 5),
                    BeadsByHairpinTask(distances = hpins)))

    beads = tuple(i for i in pair.run())[0]
    assert tuple(beads.keys()) == ('hp100',)

if __name__ == '__main__':
    test_control()
