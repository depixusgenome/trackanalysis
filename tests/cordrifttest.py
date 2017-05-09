#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests cordrift"
from   itertools                import product
from   concurrent.futures       import ProcessPoolExecutor
import random
import numpy as np
from   numpy.testing            import assert_allclose, assert_equal
from   pytest                   import approx # pylint: disable = no-name-in-module

from cordrift.collapse          import (CollapseToMean,        CollapseByDerivate,
                                        CollapseByMerging,
                                        StitchByInterpolation, Profile, _getintervals,
                                        StitchByDerivate, Range)
from cordrift.processor         import DriftTask, DriftProcessor
from simulator                  import TrackSimulator
from simulator.processor        import TrackSimulatorTask
from eventdetection.processor   import ExtremumAlignmentTask
from model.task                 import DataSelectionTask
from control.taskcontrol        import create
from testingcore                import path as utpath, DummyPool

def test_collapse_to_mean():
    "Tests interval collapses"
    yvals  = np.zeros((100,5), dtype = np.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i

    inst    = CollapseToMean(edge = None, filter = None)
    # test horizontal lines
    inters  = [Range(5, yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = inst(iter(inters))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 5)
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = np.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = inst(iter(inters[1:-1]))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 3)
    assert_allclose([-10,-5,0,5,10], prof.value, rtol = 1e-4)

    # test slanted lines + noise
    yvals[5:10,:] += np.random.rand(25).reshape((5,5))  # pylint: disable=no-member
    prof           = inst(iter(inters[1:-1]))
    assert all(prof.count == 3)
    truth = np.mean(yvals[5:10,1:-1] - np.mean(yvals[5:10,1:-1], axis = 0), axis = 1)
    assert_allclose(truth, prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = Range(15, yvals[15:25,1])
    prof      = inst(iter(inters[:-1]))
    assert all(prof.count == ([3]*5+[0]*5+[1]*10))
    assert_allclose(truth, prof.value[:5], rtol = 1e-5, atol = 1e-5)
    assert all(prof.value[5:] == 0.)

def test_collapse_by_merging():
    "Tests interval collapses"
    yvals  = np.zeros((100,5), dtype = np.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i

    inst   = CollapseByMerging(edge = None, filter = None)

    # test horizontal lines
    inters  = [Range(5, yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = inst(iter(inters))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 5)
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = np.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = inst(iter(inters[1:-1]))
    assert prof.xmin == 5
    assert prof.xmax == 10
    assert len(prof) == 5
    assert all(prof.count == 3)
    assert_allclose([-10,-5,0,5,10], prof.value, rtol = 1e-4)

    # test slanted lines + noise
    yvals[5:10,:] += np.random.rand(25).reshape((5,5))  # pylint: disable=no-member
    prof           = inst(iter(inters[1:-1]))
    assert all(prof.count == 3)
    truth = np.mean(yvals[5:10,1:-1] - np.mean(yvals[5:10,1:-1], axis = 0), axis = 1)
    assert_allclose(truth-truth[0], prof.value-prof.value[0], rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = Range(15, yvals[15:25,1])
    prof      = inst(iter(inters[:-1]))
    assert all(prof.count == ([3]*5+[0]*5+[1]*10))
    assert_allclose(truth-truth[0], prof.value[:5]-prof.value[0], rtol = 1e-5)
    assert all(prof.value[5:] == 0.)

def test_collapse_by_derivate():
    "Tests derivate collapses"
    yvals  = np.zeros((100,5), dtype = np.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i

    # test horizontal lines
    inters  = [Range(5, yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = CollapseByDerivate.run(iter(inters), edge = None, filter = None)
    assert all(prof.count == ([5]*4+[0]))
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = np.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = CollapseByDerivate.run(iter(inters[1:-1]), edge = None)
    assert all(prof.count == ([3]*4+[0]))
    assert_allclose([-20,-15,-10,-5,0], prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = Range(15, yvals[15:25,1])
    prof      = CollapseByDerivate.run(iter(inters[:-1]), edge = None)
    assert all(prof.count == ([3]*4+[0]*6+[1]*9+[0]))
    assert_allclose([-20,-15,-10,-5,0], prof.value[:5], rtol = 1e-4)
    assert all(prof.value[5:] == 0.)

def test_getinter():
    "Tests _getintervals"
    fge = lambda x: _getintervals(np.array(x), 2, np.greater_equal)
    flt = lambda x: _getintervals(np.array(x), 2, np.less)
    assert_equal(flt([2]*5+[1]*5),       [[5,10]])
    assert_equal(fge([2]*5+[1]*5),       [[0,5]])
    assert_equal(flt([1]*5+[2]*5+[1]*5), [[0,5], [10,15]])
    assert_equal(fge([1]*5+[2]*5+[1]*5), [[5,10]])

def test_stitchbyinterpolation():
    "Tests StitchByInterpolation"
    def _test(power = 1, left = False, right = False):
        prof          = Profile(60)
        prof.count[:] = 10
        prof.value = np.arange(len(prof), dtype = 'f4') ** power
        if left:
            prof.value[0] = 1
            prof.count[0] = 0
        if right:
            prof.value[-1] = prof.value[-2]
            prof.count[-1] = 0

        truth = np.array(prof.value)

        for i in range(10, len(prof), 10):
            prof.value[i:]                += random.randint(-100, 100)
            prof.count[i-i//10:i+i//10-1]  = 0

        stitched = StitchByInterpolation.run(prof,
                                             fitlength   = 3,
                                             fitorder    = power,
                                             minoverlaps = 5)
        assert_allclose(stitched.value, truth)

    for order in (1, 2):
        for left in (False, True):
            for right in (False, True):
                _test(order, left, right)

def test_stitchbyderivate():
    "Tests StitchByDerivate"

    def _test(left = False, right = False):
        prof          = Profile(60)
        prof.count[:] = 10
        prof.value = np.arange(len(prof), dtype = 'f4')
        data      = np.empty((9, 60), dtype = np.float32)
        data[:4]  = np.arange(60)**2
        data[4,:] = np.arange(len(prof), dtype = 'f4')
        data[-4:] = -np.arange(60)**3

        items     = [Range(0, i) for i in data]
        if left:
            prof.count[0] = 0
        if right:
            prof.count[-1] = 0

        truth = np.array(prof.value)

        for i in range(10, len(prof), 10):
            prof.value[i:]                += random.randint(-100, 100)
            prof.count[i-i//10:i+i//10-1]  = 0

        stitched = StitchByDerivate.run(prof, items, minoverlaps = 5)
        assert_allclose(stitched.value, truth)

    _test(True, False)
    for left in (False, True):
        for right in (False, True):
            _test(left, right)

def _run(coll, stitch, brown):
    bead   = TrackSimulator(zmax      = [0., 0., 1., 1., -.2, -.2, -.3, -.3],
                            brownian  = brown,
                            sizes     = 20,
                            ncycles   = 30,
                            drift     = (.05, 29.))
    cycles = bead.phases[0][[5,6]]
    frame  = bead.track(nbeads = 1, seed = 0).cycles
    drift  = bead.drift()[cycles[0]:cycles[1]]

    task   = DriftProcessor.newtask(filter   = None, precision = 8e-3,
                                    collapse = coll(),
                                    stitch   = stitch())
    task.events.split.confidence = None
    task.events.merge.confidence = None
    prof = DriftProcessor.profile(frame, task)
    med  = np.median(prof.value[-task.zero:])

    assert prof.xmin == 0,                      (coll, stitch)
    assert prof.xmax == 100,                    (coll, stitch)
    assert med       == approx(0., abs = 1e-7), (coll, stitch)
    if coll is CollapseByDerivate:
        return

    if brown == 0.:
        assert_allclose(prof.value[1:-1] - prof.value[-2],
                        drift[1:-1]      - drift[-2],
                        atol = 1e-5)
    else:
        diff  = prof.value-drift
        assert np.abs(diff).std() <= 1.5*brown

def _create(coll, stitch, brown):
    def _fcn():
        _run(coll, stitch, brown)
    _fcn.__name__ = 'test_%s_%s_%s' % (str(coll), str(stitch),
                                       str(brown).replace('.', 'dot'))
    return {_fcn.__name__: _fcn}

for args in product((CollapseToMean, CollapseByDerivate, CollapseByMerging),
                    (StitchByDerivate, StitchByInterpolation),
                    (0.,.003)):
    locals().update(_create(*args))
    del args
del _create

def test_beadprocess():
    "tests that tracks are well simulated"
    pair = create((TrackSimulatorTask(brownian  = 0., events = None),
                   DriftTask(precision = 0.01)))
    cycs = next(i[...,...] for i in pair.run()).withphases(5)
    for _, val in cycs:
        assert_allclose(val[1:-1], val[1:-1].mean(), rtol = 1e-5, atol = 1e-8)

    pair = create((TrackSimulatorTask(brownian  = 0.), DriftTask(precision = 0.01)))
    cycs = next(i[...,...] for i in pair.run()).withphases(5)
    for _, val in cycs:
        val = (val-np.round(val, 1))[1:-1]
        assert_allclose(val-val[0], 0., atol = 1e-2)

def test_cycleprocess():
    "tests drift removal on cycles"
    pair = create((TrackSimulatorTask(brownian  = 0.,
                                      events    = None,
                                      nbeads    = 30,
                                      ncycles   = 1),
                   DriftTask(onbeads = False, precision = 0.01)))
    cycs = next(i for i in pair.run())
    for _, val in cycs:
        val  = val[34:132]
        assert_allclose(val, val.mean(), atol = 1e-5)

    pair = create((TrackSimulatorTask(brownian  = 0.,
                                      nbeads    = 30,
                                      ncycles   = 1),
                   DriftTask(onbeads = False, precision = 0.01)))
    cycs = next(i for i in pair.run())
    for _, val in cycs:
        val  = val[34:132]
        val -= np.round(val, 1)
        assert_allclose(val-val[0], 0., atol = 1e-2)

def test_cycleprocess_withalignment():
    "tests drift removal on cycles"
    def _do(pool, drift = True):
        tasks = (utpath("big_all"),
                 DataSelectionTask(cycles = slice(2)),
                 ExtremumAlignmentTask(phase = 1),
                 DriftTask(onbeads = False))
        pair = create(tasks[:4 if drift else 3])
        ret  = dict(next(i for i in pair.run(pool = pool))[0,...].withphases(5))
        ret  = {i: j - j.mean() for i, j in ret.items()}

        cache = pair.data.getCache(-1)()
        if cache is not None:
            cache = {i[1] if isinstance(i, tuple) else i: j.value - j.value.mean()
                     for i, j in cache.items()}
        return ret, cache

    val1, prof1 = _do(None)
    val2, _     = _do(None, drift = False)
    assert np.std(val2[0,0] - val1[0,0]) >  0.001

    val2, prof2 = _do(DummyPool())
    for i, j in prof2.items():
        assert_allclose(prof1[i], j, atol = 1e-5, rtol = 1e-4)

    for i, j in val2.items():
        assert_allclose(val1[i], j, atol = 1e-5, rtol = 1e-4)

    with ProcessPoolExecutor(2) as pool:
        val2, _ = _do(pool)

    for i, j in val2.items():
        assert_allclose(val1[i], j, atol = 1e-5, rtol = 1e-4)

def test_cycleprocess_emptycycles():
    "tests drift removal on cycles"
    tasks = (utpath("big_all"),
             ExtremumAlignmentTask(phase = None),
             DriftTask(onbeads = False))
    ret = dict(next(i for i in create(tasks).run())[0,...].withphases(5))
    assert ret is not None # check that computations don't crash

if __name__ == '__main__':
    test_cycleprocess_emptycycles()
