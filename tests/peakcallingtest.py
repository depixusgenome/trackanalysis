#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"testing peakcalling"
# pylint: disable=import-error,no-name-in-module
from concurrent.futures         import ProcessPoolExecutor
from itertools                  import product
import numpy as np
from numpy.testing              import assert_allclose, assert_equal
from pytest                     import approx


from taskcontrol.taskcontrol    import create
from taskmodel.dataframe        import DataFrameTask
from simulator.processor        import ByPeaksEventSimulatorTask
from eventdetection.processor   import EventDetectionTask
from peakfinding.processor      import PeakSelectorTask
from peakfinding.histogram      import HistogramData
from peakcalling                import cost, match, Range
from peakcalling.tohairpin      import (PeakMatching, GaussianProductFit,
                                        ChiSquareFit, PeakGridFit, EdgePeaksGridFit)
from peakcalling.toreference    import HistogramFit, ChiSquareHistogramFit, Pivot
from peakcalling.processor      import (BeadsByHairpinProcessor, BeadsByHairpinTask,
                                        DistanceConstraint, FitToReferenceTask)
from testingcore                import DummyPool, path as utpath

def test_toref():
    "tests reference comparison"
    for i in product([.96, 1.], [-.05, 0., 0.05]):
        arr1 = np.array([1., 1., .5,  8.])
        arr2 = np.array([1., .5, .5,  8.])/i[0]+i[1]
        ret  = HistogramFit(maxthreshold = .5).optimize(arr1, arr2)
        assert_allclose(ret[1:], i, rtol = 5e-4, atol = 5e-4)

        ret2 = ChiSquareHistogramFit(maxthreshold = .5).optimize((arr1, np.unique(arr1)),
                                                                 (arr2, np.unique(arr2)))
        assert_allclose(ret2[1:], i, rtol = 5e-4, atol = 5e-4)

        ret2 = ChiSquareHistogramFit(maxthreshold = .5,
                                     firstregpeak = 0,
                                     pivot        = Pivot.top
                                    ).optimize((arr1, np.unique(arr1)),
                                               (arr2, np.unique(arr2)))
        assert_allclose(ret2[1:], i, rtol = 5e-4, atol = 5e-4)

        ret2 = ChiSquareHistogramFit(maxthreshold = .5,
                                     firstregpeak = 0,
                                     stretch      = Range(1., .08, .02),
                                     pivot        = Pivot.absolute
                                    ).optimize((arr1, np.unique(arr1)),
                                               (arr2, np.unique(arr2)))
        assert_allclose(ret2[1:], i, rtol = 5e-4, atol = 5e-4)

def test_toref_frompeaks():
    "tests reference comparison"
    pair = create(utpath("big_selected"), EventDetectionTask(), PeakSelectorTask())
    pks  = {i: tuple(j) for i, j in next(iter(pair.run()))}
    res  = HistogramFit().frompeaks(next(iter(pks.values())))
    ret  = HistogramFit().optimize(res, HistogramData(res.histogram,
                                                      res.minvalue+.01,
                                                      res.binwidth/1.01))

    assert_allclose(ret[1:], [1.01, .01], rtol = 5e-4, atol = 5e-4)

def test_ref_peaksgrid():
    "tests peaks grid with a single read"
    bias    = Range(0, 60.*8.8e-4, 60.*8.8e-4)
    fit     = PeakGridFit(firstpeak = True, lastpeak = True, bias = bias, pivot = Pivot.absolute)
    for i in product([.96, 1., 1.04], [-.05, 0., .05]):
        arr1 = np.array([.1, .5,  1.])
        arr2 = np.array([.1, .5,  1.])/i[0]+i[1]
        arr1 /= 8.8e-4
        fit.peaks = arr1
        ret  = fit.optimize(arr2)
        ret  = ret[1]*8.8e-4, ret[2]
        assert_allclose(ret, i, rtol = 5e-4, atol = 5e-4)

    arr1 = np.arange(50, dtype='f4').cumsum()
    arr2 = arr1/.96+0.05
    arr1 /= 8.8e-4
    fit.peaks = arr1
    ret  = fit.optimize(arr2)
    ret  = ret[1]*8.8e-4, ret[2]
    assert_allclose(ret, (.96, 0.05), rtol = 5e-4, atol = 5e-4)

def test_ref_peaksgrid_2D():
    "tests peaks grid with a top and a bottom fraction read"
    bias = Range(0, 60.*8.8e-4, 60.*8.8e-4)
    fit  = EdgePeaksGridFit(firstpeak = True, lastpeak = True, bias = bias)
    for i in product([.96, 1., 1.04], [-.05, 0., .05]):
        seq  = np.array([.01, .02,  .035, .7, .85, .95])
        arr2 = seq/i[0]+i[1]
        fit.peaks = [seq[:3]/ 8.8e-4, (seq[3:]-.5)/ 8.8e-4]
        ret  = fit.optimize(arr2)
        ret  = ret[1]*8.8e-4, ret[2][0]
        assert_allclose(ret, i, rtol = 5e-4, atol = 5e-4)

def test_toref_controller():
    "tests reference comparison"
    peaks = np.array([.1, .5, .6, 1.], dtype = 'f4')
    root  = ByPeaksEventSimulatorTask(bindings       = peaks[::-1],
                                      brownianmotion = .01,
                                      onrates        = 1.,
                                      baseline       = None,
                                      nbeads         = 1,
                                      ncycles        = 5)
    ref   = tuple(create(root).run())[0]
    tsk   = FitToReferenceTask(fitalg  = ChiSquareHistogramFit())
    tsk.frompeaks(ref)

    root.bindings = peaks[::-1]/.99 + .05
    pair          = create(root, tsk)

    beads = tuple(i for i in pair.run())[0][0]
    assert_allclose(beads.params, [.99, 0.05], rtol = 5e-3, atol = 5e-3)
    assert beads['peaks'][0] < 0
    assert beads['peaks'][1] < .17

    pair  = create(root, tsk, DataFrameTask(measures = dict(std1 = 'std',
                                                            std2 = ('std', 'mean'),
                                                            std3 = 'resolution')))
    beads = tuple(i for i in pair.run())[0][0]
    assert set(beads.index.names) == {'track', 'bead'}
    assert set(beads.columns)     == {'peakposition',      'averageduration',
                                      'hybridisationrate', 'eventcount',
                                      'referenceposition', 'std1', 'std2', 'std3'}

    pair  = create(root, tsk, DataFrameTask(measures = dict(events = True)))
    beads = tuple(i for i in pair.run())[0][0]
    assert set(beads.index.names) == {'track', 'bead', 'cycle'}
    assert set(beads.columns)     == {'peakposition',      'averageduration',
                                      'hybridisationrate', 'eventcount',
                                      'referenceposition', 'avg', 'length', 'start'}

def test_cost_value():
    u"Tests peakcalling.cost.compute"
    bead1 = np.arange(10)
    bead2 = np.arange(10)+10.
    bead3 = np.arange(10)*.5+5.
    truth = approx((0., 0., 0.))
    for sym in (False, True):
        assert cost.compute(bead1, bead1, sym, .01, 1., 0.)   == truth
        assert cost.compute(bead1, bead2, sym, .01, 1., -10.) == truth
        assert cost.compute(bead1, bead3, sym, .01, 2., -10.) == truth

        assert cost.compute(bead1, bead3, sym, .01, 1.99, -10.)[0] > 0.
        assert cost.compute(bead1, bead3, sym, .01, 1.99, -10.)[1] < 0.

        assert cost.compute(bead1, bead3, sym, .01, 2.01, -10.)[0] > 0.
        assert cost.compute(bead1, bead3, sym, .01, 2.01, -10.)[1] > 0.

        assert cost.compute(bead1, bead3, sym, .01, 2., -10.1)[0]  > 0.
        assert cost.compute(bead1, bead3, sym, .01, 2., -10.1)[2]  < 0.

        assert cost.compute(bead1, bead3, sym, .01, 2., -9.9)[0]   > 0.
        assert cost.compute(bead1, bead3, sym, .01, 2., -9.9)[2]   > 0.

def test_cost_optimize():
    u"Tests peakcalling.cost.optimize"
    bead1 = np.array([1, 5, 10], dtype = np.float32)
    bead2 = (bead1-.2)/.9
    val   = cost.optimize(bead1, bead2, False, 1., min_bias = -.5, max_bias = .5)
    assert val == approx((0., .9, .2), abs = 1e-5)

def test_match():
    u"Tests peakcalling.match.compute"
    bead1 = np.array([1, 5, 10, 32], dtype = np.float32)
    assert (match.compute(bead1, bead1-1.)-[[0,0], [1,1], [2, 2], [3, 3]]).sum() == 0
    assert (match.compute(bead1, [.8, 6., 35.])-[[0,0], [1,1], [3, 2]]).sum() == 0
    assert (match.compute(bead1, [.8, 35., 37.])-[[0,0], [3, 1]]).sum() == 0
    assert (match.compute(bead1, [-100., 5., 37.])-[[1,1], [3, 2]]).sum() == 0

def test_onehairpincost():
    u"tests hairpin cost method"
    truth = np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4
    bead  = (truth*1.03+1.)*8.8e-4
    res   = GaussianProductFit(peaks = truth).optimize(bead[:-1])
    assert_allclose((bead-res[2])*res[1], truth, rtol = 1e-4, atol = 1e-2)

def test_onehairpinid():
    u"tests haipin id method"
    truth = np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4
    bead  = np.array([0., 0.01, .1, .2, .5, 1.], dtype = 'f4') - 1.
    res   = PeakMatching(peaks = truth).pair(bead, 1./8.8e-4, -1.)
    assert_allclose(res['zvalue'], bead)
    assert_allclose(res['key'], np.insert(np.int32(truth[:-1]+.1), 1, np.iinfo('i4').min))

def test_hairpincost():
    u"tests hairpin cost method"
    truth = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4,
             np.array([0., .1,     .5, 1.2, 1.5], dtype = 'f4')/8.8e-4]

    beads = [(100, np.array([0., 0.01, .1, .2, .5, 1.], dtype = 'f4') - .88e-4),
             (101, (truth[1][:-1]*.97-1) *8.8e-4),
             (110, np.empty((0,), dtype = 'f4'))]

    hpins   = {'hp100': GaussianProductFit(peaks = truth[0]),
               'hp101': GaussianProductFit(peaks = truth[1])}
    ids     = {'hp100': PeakMatching(peaks = truth[0]),
               'hp101': PeakMatching(peaks = truth[1])}
    results = dict(BeadsByHairpinProcessor.compute(beads, hpins, {}, ids))
    assert len(results) == 3
    assert len(results['hp100']) == 1
    assert len(results['hp101']) == 1
    assert len(results['✗'])    == 1
    assert results['hp100'][0].key == 100
    assert results['hp101'][0].key == 101
    assert_equal(results['hp100'][0].peaks['key'],
                 np.insert(np.int32(truth[0][:-1]+.1), 1, np.iinfo('i4').min))
    assert_equal(results['hp101'][0].peaks['key'], np.int32(truth[1][:-1]+.1))
    assert results['✗'][0].key    == 110

    hpins   = {'hp100': ChiSquareFit(peaks = truth[0]),
               'hp101': ChiSquareFit(peaks = truth[1])}
    results = dict(BeadsByHairpinProcessor.compute(beads, hpins, {}, ids))
    assert len(results) == 3
    assert len(results['hp100']) == 1
    assert len(results['hp101']) == 1
    assert len(results['✗'])    == 1
    assert results['hp100'][0].key == 100
    assert results['hp101'][0].key == 101
    assert_equal(results['hp100'][0].peaks['key'],
                 np.insert(np.int32(truth[0][:-1]+.1), 1, np.iinfo('i4').min))
    assert_equal(results['hp101'][0].peaks['key'], np.int32(truth[1][:-1]+.1))
    assert results['✗'][0].key    == 110

def test_constrainedhairpincost():
    u"tests hairpin cost method with constraints"
    truth = [np.array([0., .1, .2, .5, 1.,  1.5], dtype = 'f4')/8.8e-4,
             np.array([0., .1,     .5, 1.2, 1.5], dtype = 'f4')/8.8e-4]

    beads = [(100, (truth[0][:-1]*1.03+1.)*8.8e-4),
             (101, (truth[1][:-1]*.97-1) *8.8e-4),
             (110, np.empty((0,), dtype = 'f4'))]

    hpins   = {'hp100': GaussianProductFit(peaks = truth[0]),
               'hp101': GaussianProductFit(peaks = truth[1])}
    cstrs   = dict.fromkeys((100, 110), DistanceConstraint('hp101', {}))

    results = dict(BeadsByHairpinProcessor.compute(beads, hpins, cstrs, {}))
    assert len(results) == 1
    assert len(results['hp101']) == 3

def test_control():
    u"tests BeadsByHairpinTask using the controller"
    peaks = np.array([0.,  .1, .5, .6, 1.], dtype = 'f4')
    truth = [np.array([0., .1, .5, 1.,       1.5], dtype = 'f4')/8.8e-4,
             np.array([0.,     .5,      1.2, 1.5], dtype = 'f4')/8.8e-4]
    hpins = {'hp100': GaussianProductFit(peaks = truth[0]),
             'hp101': GaussianProductFit(peaks = truth[1])}
    pair  = create((ByPeaksEventSimulatorTask(bindings       = peaks[::-1],
                                              brownianmotion = .01,
                                              baseline       = None,
                                              onrates        = 1.,
                                              nbeads         = 1,
                                              ncycles        = 5),
                    BeadsByHairpinTask(fit = hpins)))

    beads = tuple(i for i in pair.run())[0]
    assert tuple(beads.keys()) == ('hp100',)

    pair.clear()
    beads = tuple(i for i in pair.run(pool = DummyPool()))[0]
    assert tuple(beads.keys()) == ('hp100',)

    pair.clear()
    with ProcessPoolExecutor(2) as pool:
        beads = tuple(i for i in pair.run(pool = pool))[0]
        assert tuple(beads.keys()) == ('hp100',)

def test_peakiterator():
    "tests peaks iterator"
    ref, exp = np.array([1., 2., 5.], dtype = 'f4'), np.array([1., 2.], dtype = 'f4')
    vals = list(match.PeakIterator(ref, exp, 0., 10., -10., 10.))
    assert_allclose([i for i, _ in vals], [1., 4., 3.], rtol = 1e-3)
    assert_allclose([i for _, i in vals], [0., .75, 1./3.], rtol = 1e-3)

    vals = list(match.PeakIterator(ref, exp, 1.1, 10., -10., 10.))
    assert_allclose([i for i, _ in vals], [4., 3.], rtol = 1e-3)
    assert_allclose([i for _, i in vals], [.75, 1./3.], rtol = 1e-3)

    vals = list(match.PeakIterator(ref, exp, 0., 10., -10., .5))
    assert_allclose([i for i, _ in vals], [1., 3.], rtol = 1e-3)
    assert_allclose([i for _, i in vals], [0., 1./3.], rtol = 1e-3)

if __name__ == '__main__':
    test_constrainedhairpincost()
