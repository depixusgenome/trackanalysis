#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
# pylint: disable=import-error,no-name-in-module
import numpy
from pytest         import approx
from peakcalling    import cost, match

def test_cost_value():
    u"Tests peakcalling.cost.compute"
    bead1 = numpy.arange(10)
    bead2 = numpy.arange(10)+10.
    bead3 = numpy.arange(10)*.5+5.
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
    bead1 = numpy.array([1, 5, 10], dtype = numpy.float32)
    bead2 = (bead1-.2)/.9
    val   = cost.optimize(bead1, bead2, False, 1., min_bias = -.5, max_bias = .5)
    assert val == approx((0., .9, .2), abs = 1e-5)

def test_match():
    u"Tests peakcalling.match.compute"
    bead1 = numpy.array([1, 5, 10, 32], dtype = numpy.float32)
    assert (match.compute(bead1, bead1-1.)-[[0,0], [1,1], [2, 2], [3, 3]]).sum() == 0
    assert (match.compute(bead1, [.8, 6., 35.])-[[0,0], [1,1], [3, 2]]).sum() == 0
    assert (match.compute(bead1, [.8, 35., 37.])-[[0,0], [3, 1]]).sum() == 0
    assert (match.compute(bead1, [-100., 5., 37.])-[[1,1], [3, 2]]).sum() == 0

if __name__ == '__main__':
    test_match()
