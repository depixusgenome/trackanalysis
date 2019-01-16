#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests histogram creation and analysis"
import numpy  as np
from   numpy.testing          import assert_allclose
from   control.taskcontrol    import create
from   peakfinding.projection import (BeadProjection, CyclesDigitization,
                                      CycleProjection, ProjectionAggregator,
                                      CycleAlignment, EventExtractor, PeakListArray)
from   peakfinding.processor.projection import PeakProjectorTask
from   testingcore            import path as utfilepath

def _data():
    data = np.concatenate(sum(
        (
            [np.random.randn(10)*1e-3+i for i in (0.0, 5e-1, 2.5e-1, 0.0, -5e-2)]
            for i in range(100)
        ),
        []
    )).astype('f4')

    meas1 = np.arange(100, dtype = 'i4')*50+10
    meas2 = meas1+30
    return data, meas1, meas2

def test_cyclesdigitization():
    "test digitization"
    data  = _data()
    out   = CyclesDigitization().compute(1e-3, *data)
    assert out.maxedge > 5e-1 +5e-3
    assert -5e-2 < out.minedge < -5e-3
    assert (out.maxedge-out.minedge)/(out.nbins+1) < 5e-4

    out2  = out.compute(data[0][10:40])
    assert out2.min() >= 0
    assert out2.max() <= (out.nbins<<out.oversampling)

    prj   = CycleProjection()
    out3  = prj.compute(out, data[0][10:40])
    out4  = prj.compute(out, *data)
    assert_allclose(out3, out4[0,:], atol = 1e-6)

    prj   = ProjectionAggregator()
    out5  = prj.compute(out, out4)

    prj   = BeadProjection()
    prj.align.repeats = 0
    out6  = prj.compute(1e-3, *data).histogram
    assert_allclose(out5, out6, atol = 1e-6)

    out7 = prj.compute(1e-3, *data)
    assert len(out7.peaks) == 3

def test_eventextraction():
    "test digitization"
    data  = _data()
    prj   = BeadProjection()
    prj.align.repeats = 0
    out   = prj.compute(1e-3, *data)
    assert len(out.peaks) == 3

    evt   = EventExtractor()
    vals  = evt.compute(1e-3, out, *data)
    assert len(vals) == 100
    assert all(len(i) == 3 for i in vals)

    vals2 = evt.events(1e-3, out, *data)
    assert len(vals2) == 100
    assert all(len(i) == 3 for i in vals2)

def test_cyclealign():
    "test digitization"
    np.random.seed(0)
    data  = _data()
    digit = CyclesDigitization().compute(1e-3, *data)

    prj   = CycleProjection()
    align = CycleAlignment()
    agg   = ProjectionAggregator()

    cycs  = prj.compute(digit, *data)
    out   = align.compute(digit, agg, cycs)
    assert len(out) == 2
    assert np.all(np.abs(out[0]/digit.binwidth()).astype('i4') <= 2)
    data[0][10:40] += digit.binwidth()*5
    data[0][60:90] -= digit.binwidth()*5

    cycs  = prj.compute(digit, *data)
    out   = align.compute(digit, agg, cycs)
    assert np.all(np.abs(out[0][2:]/digit.binwidth()).astype('i4') <= 2)
    assert np.all(np.abs((out[0][:2]/digit.binwidth()).astype('i4')-[5, -5]) <= 2)

    align.repeats = 0
    out   = align.compute(digit, agg, cycs)
    assert np.abs(out[0]).sum() == 0.0

    align.repeats = 2
    out   = align.compute(digit, agg, cycs)
    assert np.all(np.abs(out[0][2:]/digit.binwidth()).astype('i4') <= 2)
    assert np.all(np.abs((out[0][:2]/digit.binwidth()).astype('i4')-[5, -5]) <= 2)

def test_task():
    "test task"
    data = next(create(utfilepath('big_selected'), PeakProjectorTask()).run())
    bead = data[0]
    assert isinstance(bead, PeakListArray)

if __name__ == '__main__':
    test_task()
