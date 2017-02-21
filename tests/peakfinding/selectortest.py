#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests peak finding"
import numpy as np
from numpy.testing              import assert_allclose
from numpy.lib.stride_tricks    import as_strided
from control.taskcontrol        import create
from simulator                  import randpeaks
from simulator.processor        import EventSimulatorTask
from peakfinding.selector       import PeakSelector
from peakfinding.processor      import PeakSelectorTask

def test_peakselector():
    u"tests peak finding"
    peaks  = [1., 5., 10., 20.]
    data   = randpeaks(5,
                       seed     = 0,
                       peaks    = peaks,
                       brownian = .1,
                       stretch  = .05,
                       bias     = .05,
                       rates    = 1.)
    events = np.array([as_strided(i, shape = (len(i), 5), strides = (i.strides[0], 0))
                       for i in data],
                      dtype = 'O')
    res    = tuple(PeakSelector()(events, precision = 1.))
    assert len(res) == 4
    assert all(len(i) == 5 for _, i in res)
    emax   = np.array([np.max([j[0] for j in i]) for _, i in res])
    emin   = np.array([np.min([j[0] for j in i]) for _, i in res])
    assert all(emax[:-1] < emin[1:])

def test_control():
    u"tests task controller"
    peaks = [1., 5., 10., 20.]
    pair  = create((EventSimulatorTask(peaks    = peaks,
                                       brownian = .01,
                                       stretch  = None,
                                       bias     = None,
                                       rates    = None,
                                       nbeads   = 2,
                                       ncycles  = 20),
                    PeakSelectorTask()))
    beads = tuple(tuple(i) for i in pair.run())[0]
    assert tuple(i[0] for i in beads) == (0, 1)

    vals = tuple(beads[0][1])
    assert_allclose([i for i, _ in vals], peaks, atol = .02)
    for peak, evts in vals:
        assert evts.dtype == 'O'
        tmp = [i.min() for i in evts]
        assert_allclose(tmp, (peak,)*20, atol = 0.1)
        tmp = [i.max() for i in evts]
        assert_allclose(tmp, (peak,)*20, atol = 0.1)

if __name__ == '__main__':
    test_control()
