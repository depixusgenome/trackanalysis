#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests that the cordrift processor runs correctly"
import numpy as np
from numpy.testing          import assert_allclose
from cordrift.processor     import BeadDriftTask
from simulator.processor    import TrackSimulatorTask
from control.taskcontrol    import TaskPair

def test_process():
    u"tests that tracks are well simulated"
    pair = TaskPair.create((TrackSimulatorTask(brownian  = 0., randtargs = None),
                            BeadDriftTask()))
    cycs = next(i[...,...] for i in pair.run()).withphases(5,5)
    for _, val in cycs:
        val -= val[-1]
        assert_allclose(val, 0., atol = 1e-8)

    pair = TaskPair.create((TrackSimulatorTask(brownian  = 0.),
                            BeadDriftTask()))
    cycs = next(i[...,...] for i in pair.run()).withphases(5,5)
    for _, val in cycs:
        val -= val[-1]
        val -= np.round(val, 1)
        assert_allclose(val, 0., atol = 1e-6)

if __name__ == '__main__':
    test_process()
