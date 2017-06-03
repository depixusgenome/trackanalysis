#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests histogram  creation and analysis"
from pathlib                    import Path
from tempfile                   import mktemp, gettempdir
import numpy as np
from numpy.testing               import assert_equal, assert_allclose
from numpy.lib.stride_tricks     import as_strided

from control.taskcontrol         import create
from simulator                   import randpeaks
from simulator.processor         import EventSimulatorTask, TrackSimulatorTask
from eventdetection.processor    import EventDetectionTask
from peakfinding.selector        import PeakSelector, EVENTS_DTYPE
from peakfinding.processor       import PeakSelectorTask, PeakProbabilityTask
from peakfinding.histogram       import (Histogram, CWTPeakFinder,
                                         ZeroCrossingPeakFinder, GroupByPeak)
from peakfinding.alignment       import PeakCorrelationAlignment
from peakfinding.reporting.batch import computereporters
from testingcore                 import path as utfilepath

CORR = lambda f, a, b, c, d, e, g: PeakCorrelationAlignment.run(f,
                                                                precision     = 1.,
                                                                oversampling  = a,
                                                                maxmove       = b,
                                                                factor        = [1.]*c,
                                                                zcost         = g,
                                                                kernel_window = d,
                                                                kernel_width  = e)

def test_correlationalignment():
    "align on best correlation"
    data = [[20, 50], [21, 51], [22, 52]]


    biases = CORR(data, 1, 5, 1, 0, .1, None)
    np.testing.assert_allclose(biases, [1., 0., -1.])

    biases = CORR(data, 5, 5, 1, 3, 2., None)
    np.testing.assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)

    biases = CORR(data, 5, 5, 1, 3, 2, 0.05)
    np.testing.assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)

def test_randcorrelationalignment():
    "align on best correlation"
    peaks, labels  = randpeaks(100,
                               peaks    = [20, 50, 60, 90],
                               rates    = .7,
                               bias     = 2.,
                               brownian = None,
                               stretch  = None,
                               seed     = 0,
                               labels   = 'range')
    biases = CORR(peaks, 5, 5, 6, 3, 2., None)
    res    = peaks+biases

    orig   = np.array([np.concatenate([pks[labs == i] for pks, labs in zip(peaks, labels)])
                       for i in range(4)])
    cured  = np.array([np.concatenate([pks[labs == i] for pks, labs in zip(res, labels)])
                       for i in range(4)])

    cstd   = np.array([i.std() for i in cured])
    ostd   = np.array([i.std() for i in orig])
    assert  all(cstd < ostd/18.)

def test_histogram():
    "tests histogram creation"
    hist = Histogram(kernel = None, precision = 1)
    events = [[np.ones((5,)), np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5                  ]]

    out, xmin, delta = hist(events, separate = False)
    out              = tuple(out)
    assert xmin     == 1
    assert delta    == .2
    assert len(out) == 1
    assert len(out[0]) == 46

    truth     = np.zeros((46,), dtype = 'f4')
    truth[0]  = 1
    truth[-1] = 2
    truth[20] = 3
    assert_equal(truth, out[0])

    hist   = Histogram(precision = 1, edge = 8)
    events = [np.ones((5,))]
    out, xmin, delta = hist(events, separate = False)
    out              = tuple(out)[0]
    assert xmin     == -7
    assert delta    == .2
    assert len(out) == 81
    assert_allclose(out[40::-1], out[40:], rtol = 1e-5, atol = 1e-10)
    assert max(out) == out[40]

def test_peakfinder():
    "tests peak finding"
    hist = Histogram(precision = 1, edge = 8)
    events = [[np.ones((5,)), np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5, np.ones((5,))*10],
              [               np.ones((5,))*5                  ]]

    out, xmin, bwidth = hist(events, separate = False)
    out   = next(out)
    truth = [1., 5., 10.]

    peaks = CWTPeakFinder()(out, xmin, bwidth)
    assert_allclose(peaks, truth, rtol = 1e-2)

    peaks = ZeroCrossingPeakFinder()(out, xmin, bwidth)
    assert_allclose(peaks, truth, rtol = 1e-2)

    peaks = ZeroCrossingPeakFinder(fitmode = 'gaussian')(out, xmin, bwidth)
    assert_allclose(peaks, truth, rtol = 1e-2)

def test_peakgroupby():
    "testing group by peaks"
    events = [[1.0, 2.0, 10.0, 20.],
              [1.1, 2.1, 10.1, 20.],
              [1.2, 2.2, 10.2, 20.],
              [0.9, 1.9, 9.9,  15.],
              [0.8, 1.8, 9.8,  20.],
              [15.]]

    peaks = [1., 2., 10., 20.]
    res   = GroupByPeak(window = 1, mincount = 5)(peaks, events)

    inf   = np.iinfo('i4').max
    assert_equal([len(i) for i in res], [4]*5+[1])
    assert_equal(np.concatenate(res), [0, 1, 2, inf]*5+[inf])

    peaks = [1.35869305, 9.76442809, 19.65128766]
    elems = [np.array([0.954, 1.798, 9.984, 20.033], dtype='f4'),
             np.array([0.564, 1.907, 10.06, 20.072], dtype='f4'),
             np.array([1.185, 1.794, 9.708, 19.396], dtype='f4'),
             np.array([1.159, 2.116, 9.692, 19.343], dtype='f4'),
             np.array([1.054, 1.928, 9.941, 19.806], dtype='f4')]
    ret   = GroupByPeak(window = 10, mincount = 5)(peaks, elems)
    for i in ret:
        assert all(i == np.array([0, 0, 1, 2]))

def test_peakselector():
    "tests peak finding"
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
    "tests task controller"
    peaks = [1., 5., 10., 20.]
    pair  = create((EventSimulatorTask(peaks    = peaks,
                                       brownian = .01,
                                       stretch  = None,
                                       bias     = None,
                                       rates    = None,
                                       baselineargs = None,
                                       nbeads   = 2,
                                       ncycles  = 20),
                    PeakSelectorTask()))
    beads = tuple(tuple(i) for i in pair.run())[0]
    assert tuple(i[0] for i in beads) == (0, 1)

    vals = tuple(beads[0][1])
    assert_allclose([i for i, _ in vals], [0.]+peaks, atol = .01, rtol = 1e-2)
    for peak, evts in vals:
        assert evts.dtype == EVENTS_DTYPE
        tmp = [i.min() for i in evts['data']]
        assert_allclose(tmp, (peak,)*20, atol = 0.1)
        tmp = [i.max() for i in evts['data']]
        assert_allclose(tmp, (peak,)*20, atol = 0.1)

def test_reporting():
    "tests processor"
    for path in Path(gettempdir()).glob("*_peakfindingtest*.xlsx"):
        path.unlink()
    out   = mktemp()+"_peakfindingtest3.xlsx"

    tasks = computereporters(dict(track    = (Path(utfilepath("big_legacy")).parent/"*.trk",
                                              utfilepath("CTGT_selection")),
                                  reporting= out))

    itms = next(tasks)
    assert not Path(out).exists()
    tuple(itms)
    assert Path(out).exists()

def test_precision():
    "tests that peaks can be found with a given precision"
    sim  = dict(durations = [15,  30,  15,  60,  60, 200,  15, 100],
                drift     = None,
                baseline  = None,
                framerate = 1.,
                poisson   = dict(rates = [.05, .05, .1, .1, .2, .2],
                                 sizes = [20,   10, 20, 10, 20, 10],
                                 peaks = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
                                 store = ['sizes']),
                seed      = 0,
                nbeads    = 2,
                ncycles   = 100)

    pair  = create(TrackSimulatorTask(**sim), EventDetectionTask(), PeakSelectorTask(),
                   PeakProbabilityTask())
    tmp   = next(pair.run())
    sim   = tmp.track.simulator[0]['sizes']
    vals  = tuple(tmp[0])

    peaks = np.array([i for i, _ in vals])
    assert_allclose(peaks, [0., .1, .2, .3, .4, .5, .6], rtol = 1e-3, atol = 1e-3)

    truth = np.sum(sim >= 5, 0)/100.
    exp   = np.array([i.hybridizationrate for _, i in vals[1:]])
    assert_allclose(exp, truth, rtol = 1e-3, atol = 1e-3)

    truth = [np.mean(i[i>=5]) for i in sim.T]
    exp   = np.array([i.averageduration for _, i in vals[1:]])
    assert_allclose(exp, truth, rtol = 1e-3, atol = 1e-3)

if __name__ == '__main__':
    test_precision()
