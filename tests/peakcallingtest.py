#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"
# pylint: disable=import-error,no-name-in-module
import numpy
from pytest         import approx
from peakcalling    import cost

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

if __name__ == '__main__':
    print("mmmm")
    test_cost_value()
