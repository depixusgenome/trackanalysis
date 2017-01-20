#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"
import numpy
from cordrift.collapse import (CollapseToMean, CollapseByDerivate,
                               StitchByInterpolation, Profile)

def test_collapse_to_mean():
    u"Tests interval collapses"
    yvals  = numpy.zeros((100,5), dtype = numpy.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i
    xvals   = numpy.arange(100)+100

    # test horizontal lines
    inters  = [(xvals[5:10], yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = CollapseToMean.run(iter(inters), edge = None)
    assert all(prof.count == 5)
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = numpy.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = CollapseToMean.run(iter(inters[1:-1]), edge = None)
    assert all(prof.count == 3)
    numpy.testing.assert_allclose([-10,-5,0,5,10], prof.value, rtol = 1e-4)

    # test slanted lines + noise
    yvals[5:10,:] += numpy.random.rand(25).reshape((5,5))  # pylint: disable=no-member
    prof  = CollapseToMean.run(iter(inters[1:-1]), edge = None)
    assert all(prof.count == 3)
    truth = numpy.mean(yvals[5:10,1:-1] - numpy.mean(yvals[5:10,1:-1], axis = 0), axis = 1)
    numpy.testing.assert_allclose(truth, prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = (xvals[15:25], yvals[15:25,1])
    prof      = CollapseToMean.run(iter(inters[:-1]), edge = None)
    assert all(prof.count == ([3]*5+[0]*5+[1]*10))
    numpy.testing.assert_allclose(truth, prof.value[:5], rtol = 1e-5)
    assert all(prof.value[5:] == 0.)

def test_collapse_by_derivate():
    u"Tests derivate collapses"
    yvals  = numpy.zeros((100,5), dtype = numpy.float32)
    for i in range(yvals.shape[1]):
        yvals[:,i] = i
    xvals   = numpy.arange(100)+100

    # test horizontal lines
    inters  = [(xvals[5:10], yvals[5:10,i]) for i in range(yvals.shape[1])]
    prof    = CollapseByDerivate.run(iter(inters), edge = None)
    assert all(prof.count == ([5]*4+[0]))
    assert all(prof.value == 0.)

    # test slanted lines
    yvals[5:10,:] = numpy.arange(25).reshape((5,5))  # pylint: disable=no-member
    prof          = CollapseByDerivate.run(iter(inters[1:-1]), edge = None)
    assert all(prof.count == ([3]*4+[0]))
    numpy.testing.assert_allclose([-20,-15,-10,-5,0], prof.value, rtol = 1e-4)

    # test non-overlapping intervals
    inters[0] = (xvals[15:25], yvals[15:25,1])
    prof      = CollapseByDerivate.run(iter(inters[:-1]), edge = None)
    assert all(prof.count == ([3]*4+[0]*6+[1]*9+[0]))
    numpy.testing.assert_allclose([-20,-15,-10,-5,0], prof.value[:5], rtol = 1e-4)
    assert all(prof.value[5:] == 0.)

def test_stitchbyinterpolation():
    u"Tests StitchByInterpolation"
    prof          = Profile(60)
    prof.count[:] = 10
    prof.value    = numpy.arange(len(prof), dtype = 'f4')
    for i in range(10, len(prof), 10):
        prof.value[i:]                += 10
        prof.count[i-i//10:i+i//10-1]  = 0

    #stitched = StitchByInterpolation.run(prof, fitlength = 3, fitorder = 1, minoverlaps = 5)
    #numpy.testing.assert_allclose(stitched.value, 1.*numpy.arange(len(stitched)))

    prof.value = numpy.arange(len(prof), dtype = 'f4')**2
    for i in range(10, len(prof), 10):
        prof.value[i:] += 10

    stitched = StitchByInterpolation.run(prof, fitlength = 3, fitorder = 2, minoverlaps = 5)
    print(stitched.value- 1.*numpy.arange(len(stitched))**2)
    numpy.testing.assert_allclose(stitched.value, 1.*numpy.arange(len(stitched))**2,
                                  atol = 1e-5, rtol = 1e-5)

if __name__ == '__main__':
    test_stitchbyinterpolation()
