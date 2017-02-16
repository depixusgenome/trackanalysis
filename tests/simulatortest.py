#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests the simulator"

import numpy as np
from   numpy.testing import assert_allclose
from   simulator import TrackSimulator, randpeaks, randbead

def test_track_simulator():
    u"testing raw data simulation"
    bead  = TrackSimulator(ncycles = 1, baselineargs = None)
    drift = bead.drift
    data  = bead(seed = 0)

    assert len(drift)       == 149
    assert np.argmax(drift) == 31
    assert drift[0]  == 0
    assert drift[-1] == 0
    assert data.shape ==  (149,)
    assert all(data == bead(seed = 0))

    data = randbead(ncycles = 5, baselineargs = None)
    assert data.shape == (149*5,)
    assert any(data[:149] != data[149:149*2])

    sim    = TrackSimulator(ncycles      = 2,
                            brownian     = None,
                            randtargs    = None,
                            baselineargs = None)
    data   = sim()
    cycles = slice(*sim.cycles[0][[5,6]])
    drift  = sim.drift[cycles]
    assert data.shape == (149*2,)
    assert all(data[:149] == data[149:149*2])
    assert_allclose(data[cycles], drift)

    bline  = TrackSimulator(baselineargs = (1., 5, False)).baseline(10)
    assert bline.shape == (10, 149)
    assert_allclose(bline.ravel(), np.cos(np.arange(1490)*.4*np.pi/149.))

    bline  = TrackSimulator(baselineargs = (1., 5, True)).baseline(2)
    assert bline.shape == (2, 149)
    assert_allclose(bline[0], [1.]*149)
    assert_allclose(bline[1], [np.cos(.4*np.pi)]*149)

def test_peak_simulator():
    u"testing peak data simulation"
    res = randpeaks(100, peaks = np.array([10, 20, 30]), rates = .5, seed = 0)
    assert len(res) == 100
    assert {len(i) for i in res} == {0, 1, 2, 3}
    vals = [i.max()-i.min() for i in res if len(i) == 3]
    assert max(*vals) > 20.
    assert min(*vals) < 20.

if __name__ == '__main__':
    test_track_simulator()
