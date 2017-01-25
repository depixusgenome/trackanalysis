#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"

import random
import numpy as np
from pytest             import approx # pylint: disable = no-name-in-module

from simulator          import BeadSimulator
from cordrift.processor import BeadDriftProcessor

def test_cordrift_task():
    u"testing the cordrift processor"
    bead   = BeadSimulator(zmax    = [0., 0., 1., 1., -.2, -.2, -.3, -.3],
                           brownian= [0.]*8,
                           ncycles = 10,
                           drift   = (.05, 29.))
    cycles = bead.cycles[0][[5,6]]
    frame  = bead.track(nbeads = 1).cycles

    task = BeadDriftProcessor.tasktype(precision = 0.008,
                                       filter    = None)
    task.events.confidence = .05
    prof = BeadDriftProcessor.profile(frame, task)
    assert prof.xmin == 0
    assert prof.xmax == 100
    assert all(prof.count[1:-1] == 10)
    assert all(prof.count[[0,-1]] == 0)
    assert np.median(prof.value[-task.zero:]) == approx(0.)
    diff = prof.value-bead.drift[cycles[0]:cycles[1]]
    np.testing.assert_allclose(diff, diff[-1], atol = 1e-7)

if __name__ == '__main__':
    random.seed(0)
    test_cordrift_task()
