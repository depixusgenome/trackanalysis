#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests that the cordrift processor runs correctly"
import numpy as np
from numpy.testing          import assert_allclose
from cordrift.processor     import BeadDriftTask
from simulator.processor    import TrackSimulatorTask
from control.taskcontrol    import create

def test_beadprocess():
    u"tests that tracks are well simulated"
    pair = create((TrackSimulatorTask(brownian  = 0., randtargs = None),
                   BeadDriftTask()))
    cycs = next(i[...,...] for i in pair.run()).withphases(5,5)
    for _, val in cycs:
        assert_allclose(val, val.mean(), rtol = 1e-5, atol = 1e-8)

    pair = create((TrackSimulatorTask(brownian  = 0.), BeadDriftTask()))
    cycs = next(i[...,...] for i in pair.run()).withphases(5,5)
    for _, val in cycs:
        val -= np.round(val, 1)
        assert_allclose(val-val[0], 0., atol = 1e-4)

def test_cycleprocess():
    u"tests that tracks are well simulated"
    pair = create((TrackSimulatorTask(brownian  = 0.,
                                      randtargs = None,
                                      nbeads    = 30,
                                      ncycles   = 1),
                   BeadDriftTask(onbeads = False)))
    cycs = next(i for i in pair.run())
    for _, val in cycs:
        val  = val[33:133]
        assert_allclose(val, val.mean(), atol = 1e-8)

    pair = create((TrackSimulatorTask(brownian  = 0.,
                                      nbeads    = 30,
                                      ncycles   = 1),
                   BeadDriftTask(onbeads = False)))
    cycs = next(i for i in pair.run())
    for _, val in cycs:
        val  = val[33:133]
        val -= np.round(val, 1)
        assert_allclose(val-val[0], 0., atol = 1e-4)

if __name__ == '__main__':
    test_beadprocess()
