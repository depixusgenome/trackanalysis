#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests the simulator"

import numpy as np
from simulator import TrackSimulator

def test_bead_simulator():
    u"testing the cordrift processor"
    bead  = TrackSimulator(ncycles = 1)
    drift = bead.drift
    data  = bead(seed = 0)

    assert len(drift)       == 149
    assert np.argmax(drift) == 31
    assert drift[0]  == 0
    assert drift[-1] == 0
    assert data.shape ==  (149,)
    assert all(data == bead(seed = 0))

    data = TrackSimulator(ncycles = 5)()
    assert data.shape == (149*5,)
    assert any(data[:149] != data[149:149*2])

    sim    = TrackSimulator(brownian  = 0., randtargs = None, ncycles = 2)
    data   = sim()
    cycles = slice(*sim.cycles[0][[5,6]])
    drift  = sim.drift[cycles]
    assert data.shape == (149*2,)
    assert all(data[:149] == data[149:149*2])
    np.testing.assert_allclose(data[cycles], drift)

if __name__ == '__main__':
    test_bead_simulator()
