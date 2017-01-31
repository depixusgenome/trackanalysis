#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Tests cordrift"

import random
import numpy as np
from   numpy.testing    import assert_allclose
from pytest             import approx # pylint: disable = no-name-in-module

from simulator              import BeadSimulator
from cordrift.processor     import BeadDriftProcessor
from cordrift.collapse      import CollapseByMerging, CollapseToMean, CollapseByDerivate

def test_cordrift_task():
    u"testing the cordrift processor"
    bead   = BeadSimulator(zmax    = [0., 0., 1., 1., -.2, -.2, -.3, -.3],
                           brownian= [0.]*8,
                           ncycles = 30,
                           drift   = (.05, 29.))
    cycles = bead.cycles[0][[5,6]]
    frame  = bead.track(nbeads = 1).cycles


    drift  = bead.drift[cycles[0]:cycles[1]]
    for cls in (CollapseToMean, CollapseByDerivate, CollapseByMerging):
        random.seed(0)
        task = BeadDriftProcessor.tasktype(filter   = None, precision = 8e-3,
                                           collapse = cls())
        task.events.split.confidence = None
        task.events.merge.confidence = None
        prof = BeadDriftProcessor.profile(frame, task)
        assert prof.xmin == 0
        assert prof.xmax == 100
        assert np.median(prof.value[-task.zero:]) == approx(0.)
        assert_allclose(prof.value-prof.value[-1],
                        drift      -drift[-1],
                        atol = 1e-7)

if __name__ == '__main__':
    test_cordrift_task()
