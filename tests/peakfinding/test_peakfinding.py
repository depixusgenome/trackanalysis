#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests histogram  creation and analysis"
from pathlib                     import Path
from tempfile                    import mktemp, gettempdir
from typing                      import cast
import numpy  as np
from numpy.testing               import assert_equal, assert_allclose

import pandas as pd

from taskmodel.dataframe         import DataFrameTask
from taskmodel.track             import InMemoryTrackTask
from taskcontrol.taskcontrol     import create
from data                        import Track
from simulator                   import randpeaks
from simulator.processor         import EventSimulatorTask, TrackSimulatorTask
from simulator.bindings          import Experiment
from eventdetection.processor    import EventDetectionTask
from peakfinding.selector        import PeakSelector, EVENTS_DTYPE
from peakfinding.processor       import (PeakSelectorTask, PeakProbabilityTask,
                                         SingleStrandTask, SingleStrandProcessor,
                                         BaselinePeakTask, MinBiasPeakAlignmentTask,
                                         GELSPeakAlignmentTask)
from peakfinding.histogram       import Histogram
from peakfinding.groupby         import CWTPeakFinder,ZeroCrossingPeakFinder, PeakFlagger
from peakfinding.alignment       import PeakCorrelationAlignment, PeakExpectedPositionAlignment
from peakfinding.reporting.batch import computereporters
from tests.testingcore           import path as utfilepath
from signalfilter                import NonLinearFilter

CORR = lambda f, a, b, c, d, e, g: PeakCorrelationAlignment.run(f,
                                                                precision     = 1.,
                                                                oversampling  = a,
                                                                maxmove       = b,
                                                                factor        = [1.]*c,
                                                                zcost         = g,
                                                                kernel_window = d,
                                                                kernel_width  = e)

def test_expectedvaluealignment():
    "align on best correlation"
    data = [[20, 50], [21, 51], [22, 52]]

    biases = PeakExpectedPositionAlignment.run(data, 1, estimations = 3)
    np.testing.assert_allclose(biases, [1., 0., -1.], atol = 1e-1)

    biases = PeakExpectedPositionAlignment.run(data, 1, estimations = 3, discardrange=.5)
    np.testing.assert_allclose(biases, [1., 0., -1.], atol = 1e-1)

def test_randexpectedvaluealignment():
    "align on best correlation"
    peaks, labels  = randpeaks(100,
                               peaks    = [20, 50, 60, 90],
                               rates    = .7,
                               bias     = 2.,
                               brownian = None,
                               stretch  = None,
                               seed     = 0,
                               labels   = 'range')
    biases = PeakExpectedPositionAlignment.run(peaks, 1, estimations = 3)
    res    = peaks+biases

    orig   = np.array([np.concatenate([pks[labs == i] for pks, labs in zip(peaks, labels)])
                       for i in range(4)])
    cured  = np.array([np.concatenate([pks[labs == i] for pks, labs in zip(res, labels)])
                       for i in range(4)])

    cstd   = np.array([i.std() for i in cured])
    ostd   = np.array([i.std() for i in orig])
    assert  all(cstd < ostd/90.)

def test_correlationalignment():
    "align on best correlation"
    data = [[20, 50], [21, 51], [22, 52]]

    biases = CORR(data, 1, 5, 1, 0, .1, None)
    np.testing.assert_allclose(biases, [1., 0., -1.])

    biases = CORR(data, 5, 5, 1, 3, 2., None)
    np.testing.assert_allclose(biases, [1., 0., -1.], rtol = 1e-4, atol = 1e-4)

    biases = CORR(data, 5, 5, 1, 3, 2, 0.001)
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
    assert  all(cstd < ostd/10.)

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
    assert_allclose(out[40::-1], out[40:], rtol = 1e-5, atol = 1e-8)
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
    res   = PeakFlagger(window = 1, mincount = 5)(peaks, events)

    inf   = np.iinfo('i4').max
    assert_equal([len(i) for i in res], [4]*5+[1])
    assert_equal(np.concatenate(res), [0, 1, 2, inf]*5+[inf])

    peaks = [1.35869305, 9.76442809, 19.65128766]
    elems = [np.array([0.954, 1.798, 9.984, 20.033], dtype='f4'),
             np.array([0.564, 1.907, 10.06, 20.072], dtype='f4'),
             np.array([1.185, 1.794, 9.708, 19.396], dtype='f4'),
             np.array([1.159, 2.116, 9.692, 19.343], dtype='f4'),
             np.array([1.054, 1.928, 9.941, 19.806], dtype='f4')]
    ret   = PeakFlagger(window = 10, mincount = 5)(peaks, elems)
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
    events = np.array([[None for j in i] for i in data])
    for i, j in zip(events, data):
        for k, val in enumerate(j):
            i[k] = np.repeat(val, 5)
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
        assert evts.dtype == 'O'
        assert all(i.dtype == EVENTS_DTYPE for i in evts)
        tmp = [i[0]['data'].min() for i in evts]
        assert_allclose(tmp, (peak,)*20, atol = 0.1)
        tmp = [i[0]['data'].max() for i in evts]
        assert_allclose(tmp, (peak,)*20, atol = 0.1)

    # test that things don't crash
    pair  = create(utfilepath('big_selected'), EventDetectionTask(), PeakSelectorTask())
    beads = tuple(next(pair.run())[0])

def test_reporting():
    "tests processor"
    for path in Path(gettempdir()).glob("*_peakfindingtest*.xlsx"):
        path.unlink()
    out   = mktemp()+"_peakfindingtest3.xlsx"

    fname = Path(cast(str, utfilepath("big_legacy"))).parent/"*.trk"
    tasks = computereporters(dict(track    = (fname,
                                              cast(str, utfilepath("CTGT_selection"))),
                                  reporting= out))

    _ = next(tasks)
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

    pair  = create(TrackSimulatorTask(**sim),
                   EventDetectionTask(filter = NonLinearFilter()),
                   PeakSelectorTask(),
                   PeakProbabilityTask())
    tmp   = next(pair.run())
    sim   = tmp.track.simulator[0]['sizes']
    vals  = tuple(tmp[0])

    peaks = np.array([i for i, _ in vals])
    assert_allclose(peaks, [0., .1, .2, .3, .4, .5, .6], rtol = 1e-3, atol = 1e-3)

    truth = np.sum(sim >= 5, 0)/100. # type: ignore
    exp   = np.array([i.hybridisationrate for _, i in vals[1:]])
    assert_allclose(exp, truth, rtol = 1e-3, atol = 1e-3)

    truth = [np.mean(i[i>=5]) for i in cast(np.ndarray, sim).T]
    exp   = np.array([i.averageduration for _, i in vals[1:]])
    assert np.all(np.abs(exp-truth) < 2)

def test_dataframe():
    "tests dataframe production"
    data = next(create(utfilepath('big_selected'),
                       EventDetectionTask(),
                       PeakSelectorTask(),
                       DataFrameTask(merge = True, measures = dict(dfevents = True))).run())
    assert isinstance(data, pd.DataFrame)
    assert 'track' in data.index.names
    assert 'bead'  in data.index.names
    assert 'peakposition' in data
    assert 'events' in data
    assert isinstance(data.events[0], pd.DataFrame)

    data = next(create(utfilepath('big_selected'),
                       EventDetectionTask(),
                       PeakSelectorTask(),
                       DataFrameTask(merge = True)).run())
    assert isinstance(data, pd.DataFrame)
    assert 'track' in data.index.names
    assert 'bead'  in data.index.names
    assert 'cycle' not in data.index.names
    assert 'peakposition' in data

    data = next(create(utfilepath('big_selected'),
                       EventDetectionTask(),
                       PeakSelectorTask(),
                       DataFrameTask(merge = True, measures = dict(events = True))).run())
    assert isinstance(data, pd.DataFrame)
    assert 'track' in data.index.names
    assert 'bead'  in data.index.names
    assert 'cycle' in data.index.names
    assert 'peakposition' in data

def test_singlestrandpeak():
    "test single strand peak"
    data  = Experiment(baseline = None, thermaldrift = None).track(seed = 1)
    track = Track(**data)
    lst   = (InMemoryTrackTask(track), EventDetectionTask(),
             PeakSelectorTask(),       SingleStrandTask())
    peaks = next(create(*lst[:-1]).run())
    proc  = SingleStrandProcessor()
    ncl   = proc.nonclosingramps(peaks, 0)
    truth = np.where(data['truth'][0].strandclosing.duration
                     >= track.phase.duration(..., range(5)))[0]
    assert set(ncl) == set(truth)

    out1  = [i for i, _ in next(create(*lst).run())[0]]
    out2  = [i for i, _ in next(create(*lst[:-1]).run())[0]]
    assert out1 == out2[:-1]

def test_baselinepeak():
    "test single strand peak"
    data  = Experiment(baseline = None, thermaldrift = None).track(seed = 1)
    track = Track(**data)
    lst   = (InMemoryTrackTask(track), EventDetectionTask(),
             PeakSelectorTask(),       BaselinePeakTask())
    out1  = [i for i, _ in next(create(*lst).run())[0]]
    out2  = [i for i, _ in next(create(*lst[:-1]).run())[0]]
    assert out1 == out2[1:]

def test_minbiasalignment():
    "test min bias alignment of peaks"
    data  = Experiment(baseline = None, thermaldrift = None).track(seed = 1)
    track = Track(**data)
    lst   = (InMemoryTrackTask(track), EventDetectionTask(),
             PeakSelectorTask(peakalign = None),
             MinBiasPeakAlignmentTask())
    peaks = next(create(*lst).run())
    _     = peaks[0]  # test everything runs

    cycles = np.array([(1. if i > 5 else 0., 0.) for i in range(10)],
                      dtype  = MinBiasPeakAlignmentTask.DTYPE)
    stats  = np.array([np.roll(cycles, i) for i in range(4)],
                      dtype  = MinBiasPeakAlignmentTask.DTYPE)
    for i in range(4):
        stats[i,:]['mean'][:] += i*10

    truth  = np.arange(10, dtype = 'f4')*.1
    truth -= np.median(truth)
    for i in range(10):
        stats[:,i]['mean'][:] -= truth[i]
    found = lst[-1](stats)
    truth = np.array([-0.44999883, -0.34998798, -0.24997711,  0., 0., 0.,  0.,
                      0.24997902,  0.34999132,  0.45000142], dtype='f4')
    assert_allclose(found, truth)

def test_gels():
    "test min bias alignment of peaks"
    data  = Experiment(baseline = None, thermaldrift = None).track(seed = 1)
    track = Track(**data)
    lst   = (InMemoryTrackTask(track), EventDetectionTask(),
             PeakSelectorTask(peakalign = None),
             GELSPeakAlignmentTask())
    peaks = next(create(*lst).run())
    _     = peaks[0]  # test everything runs

    cycles = np.array([(1. if i > 5 else 0., 0.) for i in range(10)],
                      dtype  = GELSPeakAlignmentTask.DTYPE)
    stats  = np.array([np.roll(cycles, i) for i in range(4)],
                      dtype  = GELSPeakAlignmentTask.DTYPE)
    for i in range(4):
        stats[i,:]['mean'][:] += i*10

    truth  = np.arange(10, dtype = 'f4')*.1
    truth -= np.median(truth)
    for i in range(10):
        stats[:,i]['mean'][:] -= truth[i]
    found = lst[-1](stats)

    truth = np.array([-0.47142908, -0.37142903, -0.27142864,  0.,  0., 0.,
                      0.12857169,  0.22857153,  0.32857174,  0.4285718],
                     dtype= 'f4')
    assert_allclose(found, truth)

def test_rescaling():
    "test rescaling"
    for cls in (SingleStrandTask, BaselinePeakTask):
        task = cls()
        obj  = task.rescale(5.)
        assert obj is not task
        for i, j in task.__dict__.items():
            if i in ("delta", "maxdisttozero"):
                assert abs(j*5 - obj.__dict__[i]) < 1e-5
            else:
                assert j == obj.__dict__[i]

    task = PeakSelectorTask()
    obj  = task.rescale(5.)
    assert obj is not task
    assert obj == task

if __name__ == '__main__':
    test_dataframe()
