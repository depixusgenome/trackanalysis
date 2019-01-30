#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Finds peak positions using beads as the starting data"
from typing       import Optional, Callable, Union, Tuple
import numpy as np

from signalfilter import PrecisionAlg
from utils        import initdefaults

from .selector    import PeakSelectorDetails, PRECISION
from .peaksarray  import PeakListArray, EventsArray, PeaksArray

# pylint: disable=import-error,unused-import
from ._core       import (BeadProjection, CyclesDigitization, Digitizer,
                          CycleProjectionDzPattern, CycleProjectionWeightPattern,
                          CycleProjection, ProjectionAggregator,
                          CycleAlignment, EventExtractor, BeadProjectionData)

INPUTS = Union[
    Tuple[np.ndarray, np.ndarray, np.ndarray], # bead data, phase starts, phase stops
    EventsArray
]

class PeakProjector(PrecisionAlg):
    """
    Find binding positions and selects relevant events.

    # Attributes

    * `projector`: algorithm for projecting frames onto the z axis.
    """
    rawfactor  : float              = 2.
    projector  : BeadProjection     = BeadProjection()
    extractor  : EventExtractor     = EventExtractor()
    zmeasure   : Callable           = np.nanmean
    peakmeasure: Optional[Callable] = None

    @initdefaults(frozenset(locals()) - {'rawfactor'})
    def __init__(self, **_):
        super().__init__(**_)

    def detailed(self, data: INPUTS, precision: PRECISION = None) -> PeakSelectorDetails:
        "returns computation details"
        proj, tmp, prec = self.__compute(data, precision)
        evts            = [
            (
                np.array([j[0] for j in enumerate(i) if len(j[1][1])], dtype = 'i4'),
                EventsArray([j for j in i if len(j[1])])
            )
            for i in self.extractor.events(prec, proj, *tmp)
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
        return dtl.output(self.peakmeasure)

    def __call__(self, evts, precision: PRECISION = None) -> PeakListArray:
        return self.details2output(self.detailed(evts, precision))

    def __compute(
            self, evts: INPUTS, precision: PRECISION
    )-> Tuple[BeadProjectionData, Tuple[np.ndarray, np.ndarray, np.ndarray], float]:
        if all(getattr(i, 'dtype', None) == 'f4' for i in evts):
            if (
                    len(evts)
                    and getattr(evts[0], 'dtype', np.dtype('f4')).names
                    and 'data' in evts[0].dtype.names
            ):
                evts  = [i['data'] for i in evts]

            precision = self.getprecision(precision, evts)
            data      = [
                np.concatenate(i).astype('f4') if len(i) else np.empty(0, dtype = 'f4')
                for i in evts
            ]
            ints      = (
                np.array([0]+[len(i) for i in data], dtype = 'i4')
                .cumsum(dtype = 'i4')
            )
            evts      = np.concatenate(evts), ints[:-1], ints[1:]
        else:
            assert len(evts) == 3
            precision = self.getprecision(precision, evts[0])

        proj = self.projector.compute(precision, *evts)
        return proj, evts, precision
