#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates peaks sheet
"""
from typing                 import (Tuple, Iterator,  # pylint: disable=unused-import
                                    Optional, Dict)

from excelreports.creation      import column_method, sheet_class
from data.trackitems            import BEADKEY            # pylint: disable=unused-import
from ..probabilities            import Probability
from ._base                     import Reporter, BEADKEY, PeakOutput

class Probabilities:
    "Computes and caches probabilities"
    def __init__(self, base:Reporter) -> None:
        self._proba  = Probability(framerate   = base.config.track.framerate,
                                   minduration = base.config.minduration)
        self._values = dict()   # type: Dict[Tuple[BEADKEY,int], Probability]
        self._ends   = base.config.track.durations

    def __cache(self, bead:BEADKEY, ipk:int, peak:PeakOutput) -> Probability:
        key = bead, ipk
        val = self._values.get(key, None)
        if val is not None:
            return val

        self._values[key] = val = self._proba(peak[1], self._ends)
        return val

    def __call__(self, name: str, *args):
        "returns a probability value for a bead"
        return getattr(self.__cache(*args), name)

@sheet_class("Peaks")
class PeaksSheet(Reporter):
    "Creates peaks sheet"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._neig  = None
        self._pos   = None
        self._proba = Probabilities(self)

    def iterate(self) -> Iterator[Tuple[BEADKEY, int, PeakOutput]]:
        "Iterates through peaks of each bead"
        for bead, outp in self.config.beads:
            yield from ((bead, i, peak) for i, peak in enumerate(outp))

    @staticmethod
    @column_method("Peak Position")
    def _peakpos(_1, _2, peak:PeakOutput) -> float:
        "Peak position as measured (µm)"
        return peak[0]

    @staticmethod
    @column_method("Peak Resolution")
    def _peakresolution(_1, _2, peak:PeakOutput) -> float:
        "Standard deviation of event positions (µm)"
        return Probability.resolution(peak[1])

    @column_method("Event Count")
    def _nevt(self, *args) -> int:
        "Number of events affected to this peak."
        return self._proba('nevents', *args)

    @column_method("Hybridisation Rate")
    def _hrate(self, *args) -> float:
        "Event count divided by the number of cycles"
        val = self._proba('nevents', *args)
        return val/self.config.track.ncycles

    @column_method("Hybridisation Time", units = 'seconds')
    def _averageduration(self, *args) -> float:
        """
        Average time to de-hybridization, for a frame rate of 30Hz.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)
        """
        return self._proba('averageduration', *args)

    @column_method("Hybridisation Time Probability")
    def _prob(self, *args) -> float:
        """
        Probability to de-hybridize between 2 time frames.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)
        """
        return self._proba('probability', *args)

    @column_method("Hybridisation Time Uncertainty", units = 'seconds')
    def _uncert(self, *args) -> float:
        """
        1-sigma uncertainty on the de-hybridization time:
            UNCERTAINTY ~ TIME / sqrt(NUMBER OF HYBRIDISATIONS)
        """
        return self._proba('uncertainty', *args)
