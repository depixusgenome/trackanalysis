#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates the summary sheet
"""
from   typing               import Tuple
import numpy as np

import version

from excelreports.creation  import column_method, sheet_class
from ..probabilities        import Probability
from ._base                 import BEADKEY, PeakOutput, Reporter

@sheet_class("Summary")
class SummarySheet(Reporter):
    "creates the summary sheet"
    @column_method("Signal Noise", units = 'µm')
    def _uncert(self, bead:BEADKEY, _) -> float:
        "Standard deviation of the signal"
        return self.uncertainty(bead)

    @staticmethod
    @column_method("Peak Count")
    def _npeaks(_, outp:Tuple[PeakOutput]) -> int:
        "Number of peaks detected for that bead."
        return len(outp)

    @staticmethod
    @column_method("Events per Cycle")
    def _evts(_, outp:Tuple[PeakOutput]) -> float:
        "Average number of events per cycle"
        cnt = sum(1 for _, i in outp[1:] for j in i if j is not None) # type: ignore
        if cnt == 0:
            return 0.0
        return cnt / len(outp[0][1])

    @column_method("Off Time")
    def _offtime(self, _, outp:Tuple[PeakOutput]) -> float:
        "Average time in phase 5 a bead is fully zipped"
        if len(outp) == 0:
            return 0.
        prob = Probability(framerate   = self.config.track.framerate,
                           minduration = self.config.minduration)
        prob = prob(outp[0][1], self.config.track.durations)
        return prob.averageduration

    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"
        return iter(self.config.beads)

    def info(self, cnf = ''):
        "create header"
        nbeads = len(self.config.beads)
        def _avg(fcn):
            vals = (fcn(*i) for i in self.iterate())
            return np.median([i for i in vals if i is not None])

        # pylint: disable=no-member
        items  = [("GIT Version:",      version.version()),
                  ("GIT Hash:",         version.lasthash()),
                  ("GIT Date:",         version.hashdate()),
                  ("Config:",           cnf),
                  ("Cycle  Count:",     self.config.track.ncycles),
                  ("Bead Count",        nbeads),
                  ("Median Noise:",     _avg(self._uncert)),
                  ("Events per Cycle:", _avg(self._evts)),
                  ("Off Time:",         _avg(self._offtime))
                 ]
        self.header(items)
