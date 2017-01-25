#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"

import random
import numpy as np

from simulator          import BeadSimulator
from cordrift.processor import BeadDriftProcessor

def test_cordrift_task():
    u"testing the cordrift processor"
    bead   = BeadSimulator(zmax    = [-.3, 0., 0., 1., 1., -.2, -.2, -.3],
                           ncycles = 10)
    cycles = bead.cycles[0][[5,6]]
    frame  = bead.track(nbeads = 1, seed = 0).cycles

    prof   = BeadDriftProcessor.profile(frame, {})
    assert prof.xmin == cycles[0]
    assert prof.xmax == cycles[1]
    assert all(prof.count == 10)
    np.testing.assert_allclose(prof.value, bead.drift[cycles[0]:cycles[1]])

if __name__ == '__main__':
    random.seed(0)
    test_cordrift_task()
