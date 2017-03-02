#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"

from    itertools           import product
import  numpy as np
from    numpy.testing       import assert_allclose
from    pytest              import approx # pylint: disable = no-name-in-module

from simulator              import TrackSimulator
from cordrift.processor     import DriftProcessor
from cordrift.collapse      import (CollapseByMerging, CollapseToMean,
                                    CollapseByDerivate, StitchByDerivate,
                                    StitchByInterpolation)
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

if __name__ == '__main__':
    _run(CollapseByMerging, StitchByInterpolation, 0.003)
