#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests peak finding"
import numpy as np
from numpy.lib.stride_tricks    import as_strided
from simulator                  import randpeaks
from peakfinding.selector       import PeakSelector

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

if __name__ == '__main__':
    test_peakselector()
