#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates the summary sheet
"""
from   typing                import Tuple
import numpy                 as     np
from   xlsxwriter.utility    import xl_col_to_name

import version
from   taskstore             import dumps
from   excelreports.creation import column_method, sheet_class
from ..probabilities         import Probability
from ._base                  import BEADKEY, PeakOutput, Reporter

class SigmaPeaks:
    "Creates the formula for σ[Peaks]"
    def __init__(self, parent : 'Reporter') -> None:
        peakstype     = parent.config.sheettype('peaks')
        peaks         = peakstype(parent.book, parent.config)

        self._row     = peaks.tablerow()+1
        self._formula = ''

        ind           = next(iter(peaks.columnindex('σ[Peaks]')))
        self._formula = ('=MEDIAN(INDIRECT("{sheet}!{col}:{col}"))'
                         .format(sheet = peaks.sheet_name,
                                 col   = xl_col_to_name(ind)+'{}'))

    def __call__(self, npeaks):
        "returns a chart for this bead if peak is peaks zero"
        row        = self._row+1
        self._row += npeaks
        return self._formula.format(row, self._row)

@sheet_class("Summary")
class SummarySheet(Reporter):
    "creates the summary sheet"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sigmap = SigmaPeaks(self)

    @classmethod
    def chartheight(cls, _) -> int:
        "Returns the chart height"
        return 1

    @column_method("σ[HF]", units = 'µm', fmt = '0.0000')
    def _uncert(self, bead:BEADKEY, _) -> float:
        """
        High-frequency noise.

        This is the median deviation of the movement from frame to frame
        """
        return self.uncertainty(bead)

    @column_method("σ[Peaks]",
                   units   = 'µm',
                   fmt     = '0.0000',
                   exclude = lambda x: not x.isxlsx())
    def _sigmapeaks(self, _, outp:Tuple[PeakOutput]) -> float:
        """
        Median uncertainty on peak positions.
        """
        return self._sigmap(len(outp))

    @staticmethod
    @column_method("Peak Count")
    def _npeaks(_, outp:Tuple[PeakOutput]) -> int:
        "Number of peaks detected for a given bead."
        return len(outp)

    @column_method("Valid Cycles")
    def _ncycles(self, _, outp:Tuple[PeakOutput]) -> int:
        "Number of valid cycles for a given bead."
        ncyc = self.config.track.ncycles
        if len(outp) > 0:
            ncyc -= getattr(outp[0][1], 'discarded', 0)
        return ncyc

    @column_method("Events per Cycle")
    def _evts(self, _, outp:Tuple[PeakOutput]) -> float:
        "Average number of events per cycle"
        cnt = sum(1 for _, i in outp[1:] for j in i if j is not None) # type: ignore
        if cnt == 0:
            return 0.0
        ncy = self._ncycles(_, outp)
        return 0. if ncy == 0 else (cnt / ncy)

    @column_method('Down Time Φ₅ (s)')
    def _downtime(self, _, outp:Tuple[PeakOutput]) -> float:
        "Average time in phase 5 a bead is fully zipped"
        if len(outp) == 0:
            return 0.
        prob = Probability(framerate   = self.config.track.framerate,
                           minduration = self.config.minduration)
        prob = prob(outp[0][1], self.config.track.durations)
        return prob.averageduration

    @column_method("", exclude = lambda x: not x.isxlsx())
    def _chart(self, _, outp:Tuple[PeakOutput]):
        return self.charting(outp)

    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"
        return iter(self.config.beads)

    def _info(self, cnf = ''):
        "create header"
        nbeads = len(self.config.beads)
        def _avg(fcn):
            itr  = (fcn(*i) for i in self.iterate())
            vals = [i for i in itr if i is not None]
            return np.median(vals) if vals else None

        if isinstance(cnf, list):
            strcf = dumps(cnf, indent = 4, ensure_ascii = False, sort_keys = True)
            beads = next((i.beads
                          for i in cnf if i.__class__.__name__ == 'BeadSubtractionTask'),
                         [])
            sub   = ('∅' if len(beads) == 0 else beads[0] if len(beads) ==1 else
                     ''.join(str(i) for i in beads))
        else:
            strcf = cnf
            sub   = '?'

        # pylint: disable=no-member
        return ([("Cycle Count:", self.config.track.ncycles),
                 ("Bead Count",   nbeads),
                 ("Subtracted",   sub)],
                [("σ[HF] (µm):",       _avg(self._uncert)),
                 ("Events per Cycle:", _avg(self._evts)),
                 ("Down Time Φ₅ (s):", _avg(self._downtime))],
                [("GIT Version:",      version.version()),
                 ("GIT Hash:",         version.lasthash()),
                 ("GIT Date:",         version.hashdate()),
                 ("Config:",           strcf)])

    def info(self, cnf = ''):
        "create header"
        items  = self._info(cnf)
        maxlen = max(len(i) for i in items)
        for lst in items:
            if len(lst) < maxlen:
                lst.extend((('', ''),)*(maxlen-len(lst)))

        self.header([i+('',)+j+(('',)*2)+k for i, j, k in zip(*items)])
