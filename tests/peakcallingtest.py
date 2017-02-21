#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
# pylint: disable=import-error,no-name-in-module
import numpy as np
from numpy.testing          import assert_allclose
from pytest                 import approx
from peakcalling            import cost, match
from peakcalling.processor  import (BeadsByHairpinProcessor, BeadsByHairpinTask,
                                    HairpinDistance)

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
    assert_allclose(bead*res[1]+res[2], truth, rtol = 1e-4)

def test_hairpincost():
    u"tests hairpin cost method"
    truth = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4,
             np.array([0., .1,     .5, 1.2, 1.5], dtype = 'f4')/8.8e-4]

    beads = [(100, (truth[0][:-1]*1.03+1.)*8.8e-4),
             (101, (truth[1][:-1]*.97-1) *8.8e-4),
             (110, np.empty((0,), dtype = 'f4'))]

    hpins   = {'hp100': HairpinDistance(peaks = truth[0]),
               'hp101': HairpinDistance(peaks = truth[1])}
    proc    = BeadsByHairpinProcessor(BeadsByHairpinTask(hairpins = hpins))
    results = dict(proc.apply(hpins, beads))
    assert len(results) == 3
    assert len(results['hp100']) == 1
    assert len(results['hp101']) == 1
    assert len(results[None])    == 1
    assert results['hp100'][0][0] == 100
    assert results['hp101'][0][0] == 101
    assert results[None][0][0]    == 110

if __name__ == '__main__':
    test_hairpincost()
