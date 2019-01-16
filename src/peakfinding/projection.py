#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Finds peak positions using beads as the starting data"
from typing       import Optional
import numpy as np

from signalfilter import PrecisionAlg
from utils        import initdefaults

from .selector    import PeakSelectorDetails, PRECISION
from .peaksarray  import PeakListArray, EventsArray, PeaksArray

# pylint: disable=import-error,unused-import
from ._core       import (BeadProjection, CyclesDigitization, Digitizer,
                          CycleProjectionDzPattern, CycleProjectionWeightPattern,
                          CycleProjection, ProjectionAggregator,
                          CycleAlignment, EventExtractor)

class PeakProjector(PrecisionAlg):
    """
    Find binding positions and selects relevant events.

    # Attributes

    * `projector`: algorithm for projecting frames onto the z axis.
    """
    rawfactor = 2.
    projector = BeadProjection()
    extractor = EventExtractor()
    zmeasure  = np.nanmean

    @initdefaults(frozenset(locals()) - {'rawfactor'})
    def __init__(self, **_):
        super().__init__(**_)

    def detailed(self, evts, precision: PRECISION = None) -> PeakSelectorDetails:
        "returns computation details"
        if all(getattr(i, 'dtype', None) == 'f4' for i in evts):
            precision = self.getprecision(precision, evts)
            ints      = np.array([0]+[len(i) for i in evts]).cumsum()
            evts      = np.concatenate(evts), ints[:-1], ints[1:]
        else:
            assert len(evts) == 3
            precision = self.getprecision(precision, evts[0])

        proj = self.projector.compute(precision, *evts)
        evts = [
            (
                np.array([j[0] for j in enumerate(i) if len(j[1][1])], dtype = 'i4'),
                EventsArray([j for j in i if len(j[1])])
            )
            for i in self.extractor.events(precision, proj, *evts)
        ]

        return PeakSelectorDetails(
            np.array(
                [
                    np.array([self.zmeasure(j) for j in i['data']], dtype = 'f4')
                    for _, i in evts
                ],
                dtype = 'O'
            ),
            proj.histogram,
            proj.minvalue,
            proj.binsize,
            -proj.bias,
            proj.peaks,
            PeaksArray([i for _, i in evts], dtype = 'O'),
            np.array([i for i, _ in evts], dtype = 'O')
        )

    def details2output(self, dtl: Optional[PeakSelectorDetails]) -> PeakListArray:
        "return results from precomputed details"
        if dtl is None:
            dtl = PeakSelectorDetails([], [], 0., 1., 0., [], [], []) # type: ignore
        return dtl.output(self.zmeasure)

    def __call__(self, evts, precision: PRECISION = None) -> PeakListArray:
        return self.details2output(self.detailed(evts, precision))
