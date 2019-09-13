#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests interval detection"
import pickle
from   typing                 import cast

import pandas as pd
import numpy  as np
from   numpy.testing             import assert_allclose
from   scipy.stats.distributions import chi2

from taskmodel                import PHASE
from taskmodel.dataframe      import DataFrameTask
from eventdetection.merging   import (KnownSigmaEventMerger,
                                      HeteroscedasticEventMerger,
                                      PopulationMerger, ZRangeMerger,
                                      EventSelector, PyHeteroscedasticEventMerger)
from eventdetection.splitting import (MinMaxSplitDetector, PyDerivateSplitDetector,
                                      GradedSplitDetector, PyMultiGradeSplitDetector,
                                      PyChiSquareSplitDetector, DerivateSplitDetector,
                                      ChiSquareSplitDetector,
                                      MultiGradeSplitDetector)
from eventdetection.intervalextension import (IntervalExtensionAroundMean,
                                              IntervalExtensionAroundRange)
from eventdetection.alignment import (ExtremumAlignment, CorrelationAlignment,
                                      PhaseEdgeAlignment)
from eventdetection.processor import (ExtremumAlignmentProcessor, AlignmentTactic,
                                      EventDetectionTask, ExtremumAlignmentTask,
                                      BiasRemovalTask)
from eventdetection.data      import Events
from eventdetection           import samples
from taskcontrol.taskcontrol  import create
from simulator                import randtrack
from tests.testingcore        import path as utfilepath

def test_cpp_splits():
    "test cpp splits"
    np.random.seed(0)
    data         = np.random.normal(0, 3e-3, 70).astype('f4')
    data[:10]   += 20
    data[10:20] += np.linspace(20,19,10)
    data[20:40] += 19
    data[40:45] += np.linspace(19,18,5)
    data[45:48] += 18
    data[48:53] += np.linspace(18,17,5)
    data[53:]   += 17

    der          = np.array([data[0]-np.mean(data[0:3]),
                             data[0]-np.mean(data[1:4]),
                             (data[0]*2+data[1])/3.-np.mean(data[2:5])]
                            +[np.mean(data[i-3:i])-np.mean(data[i:i+3])
                              for i in range(3, data.size-2)]
                            +[np.mean(data[-5:-2])-(data[-1]*2+data[-2])/3.,
                              np.mean(data[-4:-1])-data[-1]], dtype = 'f4')
    der  = np.abs(der)
    der /= np.percentile(der, 75.)+3e-3
    out  = DerivateSplitDetector().grade(data, 3e-3)
    assert  np.max(np.abs(out-der)) < 5e-2
    assert  np.max(np.abs(out-der/der.max()*out.max())) < 2e-5

    gx2  = np.array([np.var(data[max(0,i-2):i+3]) for i in range(data.size)], dtype = 'f4')
    gx2  = np.sqrt(gx2)
    gx2 /= 3e-3 * chi2.ppf(.9, 4)/5
    out2 = ChiSquareSplitDetector(gradewindow = 5).grade(data, 3e-3)
    assert_allclose(out2[2:-2], gx2[2:-2], rtol = 1e-6, atol = 1e-5)

    gmu        = np.copy(out)
    gmu[13:18] = out2[13:18]
    gmu[42:44] = out2[42:44]
    gmu[50:52] = out2[50:52]
    cnf        = MultiGradeSplitDetector(chisquare = ChiSquareSplitDetector(gradewindow=5),
                                         minpatchwindow= 3)
    out3       = cnf.grade(data, 3e-3)
    assert_allclose(out3, gmu)

    ints = MultiGradeSplitDetector()(data, 3e-3)
    assert tuple(tuple(i) for i in ints) == ((0,12), (19, 41), (44,49), (52, 70))

    data[1] = data[15] = data[50] = np.NaN
    ints = MultiGradeSplitDetector()(data, 3e-3)
    assert tuple(tuple(i) for i in ints) == ((0,12), (19, 41), (44,48), (52, 70))

def test_detectsplits():
    "Tests flat stretches detection"
    inst  = PyDerivateSplitDetector(precision = 1., confidence = 0.1, window = 1, erode = 0)
    det   = lambda  i: tuple(tuple(j) for j in inst(i))
    items = np.zeros((30,))
    thr   = 1.01*samples.normal.knownsigma.threshold(True, inst.confidence, inst.precision,
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

    items       = np.zeros((50,))
    items[20:] -= thr
    items[30:] -= thr
    items[31:] -= thr
    items[[10, 20, 35, 39]] = np.nan
    items[:10] = np.nan
    items[40:] = np.nan
    assert det(items) == ((0, 21), (21,30), (31,50))

    items       = np.zeros((50,))
    items[:10] = np.nan
    items[12:] -= thr
    items[20:] -= thr
    items[30:] -= thr
    items[31:] -= thr
    items[[10, 20, 35, 39]] = np.nan
    items[40:] = np.nan
    assert det(items) == ((0, 12), (12, 21), (21,30), (31,50))

def test_splittererosion():
    "tests erosion"
    class _Dummy(GradedSplitDetector):
        def _flatness(self, data):
            return data

        def _threshold(self, *_): # pylint: disable=arguments-differ
            return .9

    data = np.zeros(100, dtype = 'f4')
    data[10:20] = 1.
    data[15]    = 2.

    data[30]    = 1.

    data[40]    = 1.
    data[41]    = 2.

    data[50]    = 2.
    data[51]    = 1.

    data[60]    = 1.
    data[61]    = 2.
    data[62]    = 1.

    data[70]    = 2.
    data[71:75] = 1.

    ends = _Dummy(erode = 0, extend = None)(data)
    assert tuple(tuple(i) for i in ends) == ((0,10), (19, 30), (30, 40), (41,50),
                                             (51,60), (62, 70), (74, 100))

    ends = _Dummy(erode = 1, extend = None)(data)
    assert tuple(tuple(i) for i in ends) == ((0,11), (18, 30), (30, 41), (41,50),
                                             (50,61), (61, 70), (73, 100))

    data = np.zeros(20, dtype = 'f4')
    data[0] = 1
    data[-1] = 1
    ends = _Dummy(erode = 1, extend = None)(data)
    assert tuple(tuple(i) for i in ends) == ((0,19),)

    data = np.zeros(20, dtype = 'f4')
    data[0] = 1
    ends = _Dummy(erode = 1, extend = None)(data)
    assert tuple(tuple(i) for i in ends) == ((0,20),)

def test_chi2split():
    "Tests flat stretches detection"
    inst = PyChiSquareSplitDetector(precision = 1., confidence = None, window = 3)
    vals = np.zeros(30, dtype = 'f4')
    assert_allclose(inst.flatness(vals), vals)

    vals[5] = 1.
    res     = inst.flatness(vals)
    truth   = [0.]*4+[np.sqrt(2)/3.]*3+[0.]*23
    assert_allclose(res, truth)

def test_minmaxsplitdetector():
    "Tests flat stretches detection"
    for i in (1,3):
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

def test_intervalextension():
    "test interval extension"
    rngs = np.array([[0, 5], [7, 9], [20, 25]])
    data = np.ones(30, dtype = 'f4')
    data[7:]  += 5.
    data[9:]  += 5.
    data[15:] += 5.
    data[26:] += 5.
    data[[17,19]] += 5.
    data[27]  -= 5.

    vals = IntervalExtensionAroundMean.extend(rngs, data, 1.1, 3)
    assert_allclose(vals, [[0,7],[7,9],[18,28]])

    rngs = np.array([[0, 5], [7, 9], [20, 25]])
    vals = IntervalExtensionAroundRange.extend(rngs, data, 1.1, 3)
    assert_allclose(vals, [[0,7],[7,9],[18,28]])

    data[17]  -= 3.
    data[22]  += 2.

    rngs = np.array([[0, 5], [7, 9], [20, 25]])
    vals = IntervalExtensionAroundMean.extend(rngs, data, 1.1, 3)
    assert_allclose(vals, [[0,7],[7,9],[18,28]])

    rngs = np.array([[0, 5], [7, 9], [20, 25]])
    vals = IntervalExtensionAroundRange.extend(rngs, data, 1.1, 3)
    assert_allclose(vals, [[0,7],[7,9],[17,28]])

def test_merge():
    "Tests merging events, all at a time"
    def _merges(inst):
        "Tests flat stretches merging"
        np.random.seed(0)
        det   = lambda  i, j: tuple(tuple(_) for _ in inst(i, np.array(j, dtype ='i4')))
        items = np.random.normal(0., 1e-3, (30,)).astype('f4')

        assert det([], ((0,30),)) == tuple()
        assert det([1], tuple())  == tuple()
        assert det(items, ((0, 30),))                == ((0,30),)
        assert det(items, ((0, 10),(11,20),(22,30))) == ((0,30),)
        assert det(items, ((2, 10),(11,20),(22,28))) == ((2,28),)

        items[11:20] += 1.
        assert det(items, ((0, 10),(11,20),(22,30))) == ((0, 10),(11,20),(22,30))

        items[:10]   += 1.
        assert det(items, ((0, 10),(11,20),(22,30))) == ((0,20),(22,30))

        items[11:20] -= 1.
        assert det(items, ((0, 10),(11,20),(22,30))) == ((0,10),(11,30))

        items[25]    = np.nan
        assert det(items, ((0, 10),(11,20),(22,30))) == ((0,10),(11,30))

    _merges(KnownSigmaEventMerger(precision = 1e-3, confidence = 0.1, isequal = True,
                                  oneperrange = False))

    _merges(KnownSigmaEventMerger(precision = 1e-3, confidence = 0.1, isequal = True,
                                  oneperrange = True))
    _merges(PyHeteroscedasticEventMerger(confidence = 0.1, oneperrange = False))
    _merges(PyHeteroscedasticEventMerger(confidence = 0.1, oneperrange = True))
    _merges(HeteroscedasticEventMerger(confidence = 0.1))

    left  = np.zeros(100, dtype = 'f4')
    right = np.zeros(100, dtype = 'f4')

    left[10]    = 1
    left[20:22] = 1
    left[30:33] = 1
    left[40:43] = 1

    right[40:43] = 1

    agg = PyMultiGradeSplitDetector.AGG.patch
    assert (list(np.nonzero(agg.apply(left, right))[0])
            == [10, 20, 21, 30, 32, 40, 41, 42])

def test_population_merge():
    "tests population merge"
    data      = np.arange(100, dtype = 'f4')
    intervals = np.array([(0,10), (5,17), (8, 20), (30, 40), (37,41)], dtype = 'i4')
    merged    = PopulationMerger(percentile = 75.)(data, intervals)
    assert tuple(tuple(i) for i in merged) == ((0,10), (5,20), (30,41))

    data      = pickle.load(open(cast(str, utfilepath("eventsdata.pk")), 'rb'))
    intervals = np.array([[  1,  11], [ 12,  15], [ 16,  25], [ 26,  52],
                          [ 55, 121], [125, 136], [138, 453]], dtype = 'i4')
    merged    = PopulationMerger()(data, intervals)
    assert tuple(tuple(i) for i in merged) == ((1, 52), (55, 121), (125, 136), (138, 453))

def test_range_merge():
    "tests population merge"
    data      = np.arange(100, dtype = 'f4')
    intervals = np.array([(0,10), (5,17), (8, 23), (30, 40), (35,41)], dtype = 'i4')
    merged    = ZRangeMerger(percentile = 70.)(data, intervals)
    assert tuple(tuple(i) for i in merged) == ((0,10), (5,23), (30,41))

def test_select():
    "Tests flat stretches filtering"
    det   = lambda  i, j, k: tuple(tuple(_)
                                   for _ in EventSelector(edgelength = i, minlength = j)
                                   (np.ones(100, dtype ='f4'), np.array(k, dtype = 'i4')))
    assert det(0, 0, ((0,0),(1,1)))                 == ((0,0), (1,1))
    assert det(0, 5, ((0,0),(1,1),(5,10)))          == ((5,10),)
    assert det(1, 5, ((0,0),(1,1),(5,10), (20,30))) == ((21,29),)

    fcn         = EventSelector(edgelength = 0, minlength = 5)
    data        = np.ones(50, dtype = 'f4')
    data[:5]    = np.NaN
    data[10:15] = np.NaN
    data[:5]    = np.NaN
    data[19:20] = np.NaN

    val = fcn(data, np.array(((0,15), (10, 20)), dtype = 'i4'))
    assert [tuple(i) for i in val] == [(0, 15)]

def test_minmaxalign():
    "align on min/max value"
    data = np.zeros((5,25), dtype = np.float32)
    for i in range(5):
        data[i,:] = np.arange(25)+i*1.
    truth  = np.array([2., 1., 0., -1., -2.])

    for tpe in 'min', 'max':
        assert_allclose(ExtremumAlignment.run(data, mode = tpe), truth)

    for tpe in 'left', 'right':
        assert_allclose(PhaseEdgeAlignment.run(data, edge = tpe), truth)

def test_minmaxprocessor():
    "align on min/max value"
    track   = randtrack(driftargs = None, baselineargs = (.1, None, 'rand'))
    inipos  = [i.mean() for i in track.cycles.withphases(PHASE.initial).values()]

    bead    = ExtremumAlignmentProcessor.apply(track.beads,
                                               phase = AlignmentTactic.initial,
                                               edge  = None)
    corrpos = [i.mean() for i in bead[0,...].withphases(PHASE.initial).values()]
    assert np.std(inipos)  > .015
    assert np.std(corrpos) < .001

def test_edgeminmaxprocessor():
    "align on min/max value"
    track   = randtrack(driftargs = None, baselineargs = (.1, None, 'rand'))
    inipos  = [i.mean() for i in track.cycles.withphases(PHASE.initial).values()]

    bead    = ExtremumAlignmentProcessor.apply(track.beads,
                                               phase = AlignmentTactic.onlyinitial,
                                               edge  = 'right')
    corrpos = [i.mean() for i in bead[0,...].withphases(PHASE.initial).values()]
    assert np.std(inipos)  > .015
    assert np.std(corrpos) < .001

def test_initial_alignment():
    "align on 1 phase or another as needed"
    def _create(phase):
        track   = randtrack(driftargs = None, baselineargs = (.1, .05, 'rand'))
        ini     = track.cycles.withphases(PHASE.initial)[0,0]
        ini    += (track.cycles.withphases(PHASE.pull)[0,0].mean()-ini.mean())*.5
        bead    = ExtremumAlignmentProcessor.apply(track.beads, phase = phase)
        return [i.mean() for i in bead[0,...].withphases(PHASE.initial).values()]

    inipos  = _create(AlignmentTactic.onlyinitial)
    corrpos = _create(AlignmentTactic.initial)
    assert_allclose(inipos[1:], corrpos[1:], atol = 0.05)
    assert corrpos[0] > .4

def test_pull_alignment():
    "align on 1 phase or another as needed"
    track   = randtrack(driftargs = None, baselineargs = (.1, .05, 'rand'))
    for i in range(3):
        ini  = track.cycles.withphases(PHASE.initial)[0,i]
        ini -= ini.mean()

        pull  = track.cycles.withphases(PHASE.pull)[0,i]
        pull += .2 - pull.mean()

        meas    = track.cycles.withphases(PHASE.measure)[0,i]
        meas[:] = 0.

    pull    = track.cycles.withphases(PHASE.pull)[0,3].mean()
    meas    = track.cycles.withphases(PHASE.measure)[0,3]
    meas[:] = pull.mean()-.2

    pull    = track.cycles.withphases(PHASE.pull)[0,4].mean()
    meas    = track.cycles.withphases(PHASE.initial)[0,4]
    meas[:] = pull.mean()-.2

    bead    = ExtremumAlignmentProcessor.apply(track.beads, phase = AlignmentTactic.pull)
    inipos  = [i.mean() for i in track.beads[0,...].withphases(PHASE.pull).values()]
    corrpos = [i.mean() for i in bead       [0,...].withphases(PHASE.pull).values()]
    assert np.std(inipos[3:]) > 20*np.std(corrpos[3:])
    assert all(i < .6 for i in corrpos[:3])

def test_measure_alignment():
    "align on 1 phase or another as needed"
    track   = randtrack(driftargs = None, baselineargs = (.1, .05, 'rand'), seed = 0)
    for i in range(3):
        ini  = track.cycles.withphases(PHASE.initial)[0,i]
        ini += (track.cycles.withphases(PHASE.pull)[0,i].mean()-ini.mean())*.5

    for i in range(5):
        ini  = track.cycles.withphases(PHASE.measure)[0,i]
        ini += (track.cycles.withphases(PHASE.pull)[0,i].mean()-ini.mean())*.5

    bead    = ExtremumAlignmentProcessor.apply(track.beads, phase = AlignmentTactic.measure)
    inipos  = [i.mean() for i in # type: ignore
               track.beads[0,...].withphases(PHASE.pull).values()]
    corrpos = [i.mean() for i in # type: ignore
               bead[0,...].withphases(PHASE.pull).values()]
    assert np.std(inipos[3:]) > 10*np.std(corrpos[3:])
    assert all(i > .95 for i in corrpos[:3])

def test_correlationalignment():
    "align on best correlation"
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

    data  = track.beads.new(Events)
    found = np.array([len(i) for _, i in data[0,...]], dtype = 'i4')
    sizes = getattr(track, 'simulator')[0]['sizes']
    sim   = np.sum(sizes >= data.events.select.minduration, 1)
    assert list(np.nonzero(found-sim-1)[0]) == []

def test_dataframe():
    "tests dataframe production"
    data = next(create(utfilepath('big_selected'),
                       EventDetectionTask(),
                       DataFrameTask(merge = True)).run())
    assert isinstance(data, pd.DataFrame)
    assert 'track' in data.index.names
    assert 'bead'  in data.index.names
    assert 'cycle' in data.index.names
    assert 'event' in data.index.names
    assert 'avg'   in data
    assert 'modification' in data.columns
    assert hasattr(data, 'tasklist')

def test_rescale():
    "test rescale"
    task = EventDetectionTask()
    obj  = task.rescale(5.)
    assert obj.events.select.__getstate__() == task.events.select.__getstate__()
    dumps = pickle.dumps
    assert dumps(obj.events.split) == dumps(task.events.split)
    assert dumps(obj.events.merge.pop) == dumps(task.events.merge.pop)
    assert dumps(obj.events.merge.range) == dumps(task.events.merge.range)
    assert obj.events.merge.stats.confidence == task.events.merge.stats.confidence
    assert (obj.events.merge.stats.minprecision - task.events.merge.stats.minprecision*5.) < 1e-6

    task = ExtremumAlignmentTask()
    obj  = task.rescale(5.)
    for i, j in task.__dict__.items():
        if i in ('delta', 'minrelax', 'pull', 'opening'):
            assert abs(getattr(obj, i) - j*5) < 1e-6
        else:
            assert getattr(obj, i)  == j

    task = BiasRemovalTask()
    obj  = task.rescale(5.)
    for i, j in task.__dict__.items():
        if i in ('zerodelta', 'binsize'):
            assert abs(getattr(obj, i) - j*5) < 1e-6
        else:
            assert getattr(obj, i)  == j

if __name__ == '__main__':
    test_select()
    test_minmaxprocessor()
