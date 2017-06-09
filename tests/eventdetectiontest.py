#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests interval detection"

import numpy  as np
from   numpy.testing          import assert_allclose
from model                    import PHASE
from eventdetection.detection import (DerivateSplitDetector, EventMerger, EventSelector,
                                      MinMaxSplitDetector, tocycles)
from eventdetection.alignment import (ExtremumAlignment, CorrelationAlignment,
                                      PhaseEdgeAlignment)
from eventdetection.processor import ExtremumAlignmentProcessor, AlignmentTactic
from eventdetection.data      import Events
from simulator                import randtrack
from signalfilter             import samples

def test_detectsplits():
    u"Tests flat stretches detection"
    inst  = DerivateSplitDetector(precision = 1., confidence = 0.1, window = 1)
    det   = lambda  i: tuple(tuple(j) for j in inst(i))
    items = np.zeros((30,))
    thr   = samples.normal.knownsigma.threshold(True, inst.confidence, inst.precision,
                                                inst.window, inst.window)

    assert det([])    == tuple()
    assert det(items) == ((0, 30),)

    items[10:] -= thr
    items[20:] -= thr
    items[21:] -= thr
    assert det(items) == ((0, 10), (10,20), (21,30))

    items[0:2]  = (2*thr, thr)
    items[28:] -= thr
    items[29:] -= thr
    assert det(items) == ((2, 10), (10,20), (21,28))

    items       = np.zeros((30,))
    items[10:] -= thr
    items[20:] -= thr
    items[21:] -= thr
    items[[0, 10, 25, 29]] = np.nan
    assert det(items) == ((0, 11), (11,20), (21,30))

def test_multiscalesplits():
    u"Tests flat stretches detection"
    for i in range(1,3):
        inst  = MinMaxSplitDetector(precision  = 1.,
                                    confidence = 0.1,
                                    window     = i)
        det   = lambda k: tuple(tuple(j) for j in inst(k))
        items = np.zeros((30,))
        thr   = samples.normal.knownsigma.threshold(True, inst.confidence, inst.precision)
        thr  *= 1.0001

        assert det([])    == tuple()
        assert det(items) == ((0, 30),)

        items[10:] -= thr
        items[20:] -= thr
        items[21:] -= thr
        assert det(items) == ((0, 10), (10,20), (21,30))

        items[0:2]  = (2*thr, thr)
        items[28:] -= thr
        items[29:] -= thr
        assert det(items) == ((2, 10), (10,20), (21,28))

        items       = np.zeros((30,))
        items[10:] -= thr
        items[20:] -= thr
        items[21:] -= thr
        items[[0, 10, 25, 29]] = np.nan
        assert det(items) == ((0, 11), (11,20), (21,30))

def _merges(oneperrange):
    u"Tests flat stretches merging"
    inst  = EventMerger(precision = 1., confidence = 0.1, isequal = True,
                        oneperrange = oneperrange)
    det   = lambda  i, j: tuple(tuple(_) for _ in inst(i, np.array(j)))
    items = np.zeros((30,))

    assert det([], ((0,30),)) == tuple()
    assert det([1], tuple())  == tuple()
    assert det(items, ((0, 30),))                == ((0,30),)
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,30),)
    assert det(items, ((2, 10),(11,20),(22,28))) == ((2,28),)

    items[11:20] = 1000.
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0, 10),(11,20),(22,30))

    items[:20] = 1000.
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,20),(22,30))

    items[11:] = 0.
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,10),(11,30))

    items[11:] = 0.
    items[25]  = np.nan
    assert det(items, ((0, 10),(11,20),(22,30))) == ((0,10),(11,30))

def test_fastmerge():
    u"Tests merging events, all at a time"
    _merges(False)

def test_slowmerge():
    u"Tests merging events, one by one"
    _merges(True)

def test_select():
    u"Tests flat stretches filtering"
    det   = lambda  i, j, k: tuple(tuple(_)
                                   for _ in EventSelector(edgelength = i, minlength = j)
                                   (np.array(k)))
    assert det(0, 0, ((0,0),(1,1)))                 == ((0,0), (1,1))
    assert det(0, 5, ((0,0),(1,1),(5,10)))          == ((5,10),)
    assert det(1, 5, ((0,0),(1,1),(5,10), (20,30))) == ((21,29),)

def test_tocycles():
    u"Tests interval assignment to cycles"
    starts = np.arange(10)*10
    inters = ((0,5), (3, 5), (0,15), (2, 21), (11,15), (11, 22), (16, 33),
              (80, 89), (80, 90), (80, 91), (83, 100), (83, 101), (90,120),
              (95, 95), (88, 88))
    inters = tuple(slice(*i) for i in inters)

    truth  = (0, 0, 0, 1, 1, 1, 2, 8, 8, 8, 9, 9, 9, 9, 8)
    vals   = tuple(i.cycle for i in tocycles(starts, inters))
    assert vals == truth

def test_minmaxalign():
    u"align on min/max value"
    data = np.zeros((5,25), dtype = np.float32)
    for i in range(5):
        data[i,:] = np.arange(25)+i*1.
    truth  = np.array([2., 1., 0., -1., -2.])

    for tpe in 'min', 'max':
        assert_allclose(ExtremumAlignment.run(data, mode = tpe), truth)

    for tpe in 'left', 'right':
        assert_allclose(PhaseEdgeAlignment.run(data, edge = tpe), truth)

def test_minmaxprocessor():
    u"align on min/max value"
    track   = randtrack(driftargs = None, baselineargs = (.1, None, 'rand'))
    inipos  = [i.mean() for i in track.cycles.withphases(PHASE.initial).values()]

    bead    = ExtremumAlignmentProcessor.apply(track.beadsonly,
                                               phase = AlignmentTactic.initial,
                                               edge  = None)
    corrpos = [i.mean() for i in bead[0,...].withphases(PHASE.initial).values()]
    assert np.std(inipos)  > .015
    assert np.std(corrpos) < .001

def test_edgeminmaxprocessor():
    u"align on min/max value"
    track   = randtrack(driftargs = None, baselineargs = (.1, None, 'rand'))
    inipos  = [i.mean() for i in track.cycles.withphases(PHASE.initial).values()]

    bead    = ExtremumAlignmentProcessor.apply(track.beadsonly,
                                               phase = AlignmentTactic.onlyinitial,
                                               edge  = 'right')
    corrpos = [i.mean() for i in bead[0,...].withphases(PHASE.initial).values()]
    assert np.std(inipos)  > .015
    assert np.std(corrpos) < .001

def test_initial_alignment():
    u"align on 1 phase or another as needed"
    def _create(phase):
        track   = randtrack(driftargs = None, baselineargs = (.1, .05, 'rand'))
        ini     = track.cycles.withphases(PHASE.initial)[0,0]
        ini    += (track.cycles.withphases(PHASE.pull)[0,0].mean()-ini.mean())*.5
        bead    = ExtremumAlignmentProcessor.apply(track.beadsonly, phase = phase)
        return [i.mean() for i in bead[0,...].withphases(PHASE.initial).values()]

    inipos  = _create(AlignmentTactic.onlyinitial)
    corrpos = _create(AlignmentTactic.initial)
    assert_allclose(inipos[1:], corrpos[1:], atol = 0.05)
    assert corrpos[0] > .4

def test_pull_alignment():
    u"align on 1 phase or another as needed"
    track   = randtrack(driftargs = None, baselineargs = (.1, .05, 'rand'))
    for i in range(3):
        ini  = track.cycles.withphases(PHASE.initial)[0,i]
        ini += (track.cycles.withphases(PHASE.pull)[0,i].mean()-ini.mean())*.5

        meas    = track.cycles.withphases(PHASE.measure)[0,i]
        meas[:] = ini.mean()

    for i in range(3,5):
        ini  = track.cycles.withphases(PHASE.initial)[0,i]
        ini += (track.cycles.withphases(PHASE.pull)[0,i].mean()-ini.mean())*.5

    bead    = ExtremumAlignmentProcessor.apply(track.beads, phase = AlignmentTactic.pull)
    inipos  = [i.mean() for i in track.beads[0,...].withphases(PHASE.pull).values()]
    corrpos = [i.mean() for i in bead       [0,...].withphases(PHASE.pull).values()]
    assert np.std(inipos[3:]) > 40*np.std(corrpos[3:])
    assert all(i < .6 for i in corrpos[:3])

def test_measure_alignment():
    u"align on 1 phase or another as needed"
    track   = randtrack(driftargs = None, baselineargs = (.1, .05, 'rand'))
    for i in range(3):
        ini  = track.cycles.withphases(PHASE.initial)[0,i]
        ini += (track.cycles.withphases(PHASE.pull)[0,i].mean()-ini.mean())*.5

    for i in range(5):
        ini  = track.cycles.withphases(PHASE.measure)[0,i]
        ini += (track.cycles.withphases(PHASE.pull)[0,i].mean()-ini.mean())*.5

    bead    = ExtremumAlignmentProcessor.apply(track.beads, phase = AlignmentTactic.measure)
    inipos  = [i.mean() for i in track.beads[0,...].withphases(PHASE.pull).values()]
    corrpos = [i.mean() for i in bead       [0,...].withphases(PHASE.pull).values()]
    assert np.std(inipos[3:]) > 10*np.std(corrpos[3:])
    assert all(i > .95 for i in corrpos[:3])

def test_correlationalignment():
    u"align on best correlation"
    data = [np.zeros((100,)) for i in range(3)]
    for i in range(3):
        data[i][20+i] = 1.
        data[i][50+i] = 1.

    corr = lambda f, a, b, c, d, e: (CorrelationAlignment.run(f,
                                                              oversampling  = a,
                                                              maxcorr       = b,
                                                              nrepeats      = c,
                                                              kernel_window = d,
                                                              kernel_width  = e))

    biases = corr(data, 1, 2, 1, 0, .1)
    assert_allclose(biases, [1., 0., -1.])

    biases = corr(data, 5, 2, 1, 3, 2.)
    assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)

def test_precision():
    "tests that peaks can be found with a given precision"
    track  = randtrack(durations = [15,  30,  15,  60,  60, 200,  15, 100],
                       drift    = None,
                       baseline = None,
                       poisson  = dict(rates = [.05, .05, .1, .1, .2, .2],
                                       sizes = [20,   10, 20, 10, 20, 10],
                                       peaks = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                                       store = ['sizes']),
                       seed     = 0,
                       nbeads   = 1,
                       ncycles  = 100)

    data  = track.beadsonly.new(Events)
    found = np.array([len(i) for _, i in data[0,...]], dtype = 'i4')
    sizes = getattr(track, 'simulator')[0]['sizes']
    sim   = np.sum(sizes >= data.events.select.minduration, 1)
    assert list(np.nonzero(found-sim-1)[0]) == []

if __name__ == '__main__':
    test_pull_alignment()
