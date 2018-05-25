#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests the simulator"
from    itertools       import product
import  numpy as np
from    numpy.testing   import assert_allclose
from    simulator       import (TrackSimulator, randpeaks, randbead, randevents,
                                randbypeakevents)
import simulator.bindings as _bind

def test_track_simulator():
    u"testing raw data simulation"
    bead  = TrackSimulator(ncycles = 1, baseline = None)
    drift = bead.drift()
    data  = bead(seed = 0)

    assert len(drift)       == 149
    assert np.argmax(drift) == 31
    assert drift[0]  == 0
    assert drift[-1] == 0
    assert data.shape ==  (149,)
    assert all(data == bead(seed = 0))

    data = randbead(ncycles = 5, baseline = None)
    assert data.shape == (149*5,)
    assert any(data[:149] != data[149:149*2])

    sim    = TrackSimulator(ncycles  = 2,
                            brownian = None,
                            events   = None,
                            closing  = None,
                            baseline = None)
    data   = sim()
    cycles = slice(*sim.phases[0][[5,6]])
    drift  = sim.drift()[cycles]
    assert data.shape == (149*2,)
    assert all(data[:149] == data[149:149*2])
    assert_allclose(data[cycles], drift)

    bline  = TrackSimulator(baseline = (1., 5, 'cos')).baseline(10)
    assert bline.shape == (10, 149)
    assert_allclose(bline.ravel(), np.cos(np.arange(1490)*.4*np.pi/149.))

    bline  = TrackSimulator(baseline = (1., 5, 'stairs')).baseline(2)
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

def test_events_simulator():
    u"testing event simulation"
    ares = randevents(2, ncycles = 100, peaks = np.array([.1, .2, .5]), rates = .5, seed = 0)
    assert frozenset(ares.keys()) == frozenset(product(range(2), range(100)))

    res  = tuple(ares[0,i] for i in range(100))
    assert {len(i) for i in res} == {1, 2, 3, 4}
    elem = next(i for i in res if len(i))
    assert elem.dtype == np.dtype([('start', 'i4'), ('data', 'O')])

def test_bypeaksevents_simulator():
    u"testing event simulation"
    ares = randbypeakevents(1, seed  = 0,
                            ncycles  = 100,
                            peaks    = np.array([.1, .2, .5]),
                            rates    = .5,
                            brownian = None,
                            drift    = None,
                            baseline = None)
    res  = tuple(ares)
    assert len(res) == 1
    assert res[0][0] == 0
    res2 = tuple(res[0][1])
    assert_allclose([i for i, _ in res2], [.0, .1, .2, .5], atol = 1e-5)
    for i, j in res2:
        for k in j['data']:
            if k is None:
                continue
            assert np.abs(k-i).sum() < 1e-3

def test_bindings():
    "test bindings"
    exp  = _bind.Experiment(brownianmotion = None, ncycles = 100, onrates = 1., offrates = 100.)
    vals = exp.eventdurations(seed = 0)
    assert vals.shape == (100, len(exp.bindings))
    assert np.all(np.cumsum(vals, axis = 1) <= exp.phases['measure'])

    exp  = _bind.Experiment(brownianmotion = None, ncycles = 100, onrates = 1., offrates = 0.)
    vals = exp.eventdurations(seed = 0)
    assert vals.shape == (100, len(exp.bindings))
    assert np.all(np.cumsum(vals, axis = 1) <= exp.phases['measure'])
    assert np.all(np.cumsum(vals, axis = 1) > 0)

    exp  = _bind.Experiment(brownianmotion = None, ncycles = 100, onrates = 0.)
    bead = exp.bead(seed = 0)[1]
    assert bead.size == 100*np.sum(exp.phases)

    exp  = _bind.Experiment(brownianmotion = None, ncycles = 100, onrates = 1.)
    trks = exp.track(nbeads = 2, seed = 0)
    assert set(trks) == {'framerate', 'key', 'data', 'truth', 'phases'}
    assert set(trks['data']) == {0, 1}

    exp  = _bind.Experiment(brownianmotion = 3e-3,
                            ncycles = 100,
                            onrates = .8,
                            offrates = 10,
                            thermaldrift = True,
                            baseline = True,)
    trks = exp.track(nbeads = 2, seed = 0)
    assert set(trks) == {'framerate', 'key', 'data', 'truth', 'phases'}
    assert set(trks['data']) == {0, 1}

    exp  = _bind.Experiment(brownianmotion = None,
                            ncycles = 100,
                            onrates = .3,
                            offrates = 10,
                            thermaldrift = None,
                            baseline = None,)
    trks = exp.track(nbeads = 2, seed = 0)
    assert set(trks) == {'framerate', 'key', 'data', 'truth', 'phases'}
    assert set(trks['data']) == {0, 1}

if __name__ == '__main__':
    test_bindings()
