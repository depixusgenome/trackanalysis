#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Tests histogram creation and analysis"
import numpy  as np
from   numpy.testing          import assert_allclose
from   peakfinding.projection import (BeadProjection, CyclesDigitization,
                                      CycleProjection, ProjectionAggregator,
                                      CycleAlignment)

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
    assert_allclose(out3, out4[0,:])

    prj   = ProjectionAggregator()
    out5  = prj.compute(out, out4)

    prj   = BeadProjection()
    out6  = prj.compute(1e-3, *data).histogram
    assert_allclose(out5, out6)

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

if __name__ == '__main__':
    test_cyclealign()
