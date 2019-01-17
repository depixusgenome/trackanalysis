#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates the summary sheet
"""
from   typing                     import Optional
import numpy                      as     np
from   xlsxwriter.utility         import xl_col_to_name

import version
from   taskstore                  import dumps
from   peakfinding.probabilities  import Probability
from   excelreports.creation      import column_method, sheet_class
from   ._base                     import Bead, Reporter, Group

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

    @staticmethod
    def chartheight(npeaks:int) -> int:
        "Returns the chart height"
        return 1

    @column_method("Newly Clustered", exclude = Reporter.nohairpin)
    def _identified(self, _, bead:Bead) -> Optional[bool]:
        """
        Whether the bead was clustered now or whether its reference comes from
        a previous report
        """
        return None if bead is None else bead.key not in self.config.knownbeads

    @column_method("σ[HF]", units = 'µm', fmt = '0.0000')
    def _uncert(self, _, bead:Bead) -> Optional[float]:
        """
        High-frequency noise.

        This is the median deviation of the movement from frame to frame
        """
        return None if bead is None else self.uncertainty(bead)

    @column_method("σ[Peaks]",
                   units   = 'µm',
                   fmt     = '0.0000',
                   exclude = lambda x: not x.isxlsx())
    def _sigmapeaks(self, ref:Group, bead:Bead) -> Optional[float]:
        """
        Median uncertainty on peak positions.
        """
        if bead is None:
            if ref.key not in self.config.hairpins:
                return None
            npeaks = len(self.config.hairpins[ref.key].peaks[:-1])
            return self._sigmap(npeaks)
        return self._sigmap(len(bead.peaks))

    @staticmethod
    @column_method("Silhouette", cond = dict(type = 'data_bar'))
    def _silh(_, bead:Bead) -> Optional[float]:
        """
        Silhouette of the bead: cluster quality factor.
        Values range from -1 (bad) to 1. (good).

        The formula is:
            - a = distance to the current cluster's reference bead
            - b = minimum distance to other reference beads
            => silhouette = 2.*(b-a)/max(a,b)-1.
        """
        return None if bead is None else bead.silhouette

    @staticmethod
    @column_method("Distance")
    def _dist(_, bead:Bead) -> Optional[float]:
        """
        distance to group's central bead:
        how likely this beads belongs to the group
        """
        return None if bead is None else bead.distance.value

    @staticmethod
    @column_method("Stretch", units = lambda x: None if x.nohairpin() else 'base/µm')
    def _stretch(_, bead:Bead) -> Optional[float]:
        """
        Parameter A in the formula "x_hpin = A*(x_bead-B)"
        converting this bead's peak position axis to
        the hairpin's.
        """
        return None if bead is None else bead.distance.stretch

    @staticmethod
    @column_method("Bias", units = 'µm')
    def _bias(_, bead:Bead) -> Optional[float]:
        """
        Parameter B in the formula "x_hpin = A*(x_bead-B)"
        converting this bead's peak position axis to
        the hairpin's.
        """
        return None if bead is None else bead.distance.bias

    @column_method("Chi²")
    def _chi2(self, _, bead:Bead) -> Optional[float]:
        "How linear the relationship between peaks is."
        if bead is None:
            return None

        good = bead.peaks['key'] >= 0
        if not any(good):
            return None

        dist = bead.distance
        chi2 = (((bead.peaks['zvalue'][good]-dist.bias)*dist.stretch
                 -bead.peaks['key'][good])**2).mean()
        return chi2/((dist.stretch*self.uncertainty(bead))**2)

    @column_method("Peak Count")
    def _npeaks(self, ref:Group, bead:Bead) -> Optional[int]:
        """Number of peaks detected for that bead."""
        if bead is None:
            if ref.key not in self.config.hairpins:
                return None
            return len(self.config.hairpins[ref.key].peaks[:-1])
        return len(bead.peaks)

    @column_method("Unidentified Peak Count", exclude = Reporter.nohairpin)
    def _unidentifiedpeaks(self, ref, bead:Bead) -> Optional[int]:
        """
        For an experimental bead:

            Number of peaks detected for that bead
            that were not found in the reference.

        For a reference:

            Number of peaks never seen
        """
        # ignore first peak which is always set to zero in the ref
        if bead is None:
            if ref.key not in self.config.hairpins:
                return None

            peaks = self.config.hairpins[ref.key].peaks[1:-1]
            theor = set(np.int32(peaks+.1)) # type: ignore
            for itm in ref.beads:
                theor.difference_update(itm.peaks['key'])
            return len(theor)

        return (bead.peaks['key'][1:] < 0).sum()

    @column_method("Identified Peak Ratio")
    def _identified_ratio(self, ref:Group, bead:Bead) -> Optional[str]:
        """Identified peaks / Expected peaks"""
        npks   = self._npeaks(ref, bead)
        ntheo  = self._npeaks(ref, None)
        nundef = self._unidentifiedpeaks(ref, bead)
        if None in (npks, nundef, ntheo) or ntheo == 0:
            return None
        return '{}%'.format(int(100.*(npks-nundef)/ntheo))

    @column_method("Unknown Peak Ratio")
    def _unknown_ratio(self, ref:Group, bead:Bead) -> Optional[str]:
        """Unknown peaks/ Found peaks"""
        npks   = self._npeaks(ref, bead)
        nundef = self._unidentifiedpeaks(ref, bead)
        if None in (npks, nundef) or npks == 0:
            return None
        return '{}%'.format(int(100.*nundef/npks))

    @column_method("Valid Cycles")
    def _ncycles(self, _, bead:Bead) -> Optional[int]:
        "Number of valid cycles for a given bead."
        return None if bead is None else self.beadncycles(bead)

    @column_method("Events per Cycle")
    def _evts(self, _, bead:Bead) -> Optional[float]:
        "Average number of events per cycle"
        if bead is None:
            return None

        cnt = sum(1 for _, i in bead.events[1:] for j in i if j is not None) # type: ignore
        if cnt == 0:
            return 0.0
        return cnt / self.beadncycles(bead)

    @column_method('Down Time Φ₅ (s)')
    def _downtime(self, _, bead:Bead) -> Optional[float]:
        "Average time in phase 5 a bead is fully zipped"
        if bead is None:
            return None

        prob = Probability(framerate   = self.config.track.framerate,
                           minduration = self.config.minduration)
        if len(bead.events) == 0:
            return Probability.FMAX

        prob = prob(bead.events[0][1], self.config.track.durations) # type: ignore
        return prob.averageduration

    @column_method("", exclude = lambda x: not x.isxlsx())
    def _chart(self, *args):
        return self.charting(*args)

    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"
        for group in self.config.groups:
            yield (group, None)
            yield from ((group, bead) for bead in group.beads)

    def tablerow(self):
        return len(self.__info('', True))+2

    def info(self, cnf = ''):
        "create header"
        self.header(self.__info(cnf, False))

    def __info(self, cnf, sizeonly):
        "creates the header table"
        nbeads = 0 if sizeonly else sum(len(i.beads) for i in self.config.groups)
        def _avg(fcn):
            if sizeonly:
                return None
            vals = (fcn(*i) for i in self.iterate())
            good = [i for i in vals if i is not None]
            return None if len(good) == 0 else np.median(good)

        if isinstance(cnf, list):
            strcf = dumps(cnf, indent = 4, ensure_ascii = False, sort_keys = True)
            beads = next((i.beads
                          for i in cnf if i.__class__.__name__ == 'BeadSubtractionTask'),
                         [])
            sub   = ('∅' if len(beads) == 0 else beads[0] if len(beads) ==1 else
                     ''.join(str(i) for i in beads))
        else:
            strcf = cnf
            sub   = ''

        # pylint: disable=no-member
        items = ([("Oligos:",      ', '.join(self.config.oligos)),
                  ("Cycle Count:", self.config.track.ncycles),
                  ("Bead Count",   nbeads),
                  ("Subtracted",   sub)],
                 [("σ[HF] (µm):",       _avg(self._uncert)),
                  ("Events per Cycle:", _avg(self._evts)),
                  ("Down Time Φ₅ (s):", _avg(self._downtime))],
                 [("GIT Version:",      version.version()),
                  ("GIT Hash:",         version.lasthash()),
                  ("GIT Date:",         version.hashdate()),
                  ("Config:",           strcf)])

        maxlen = max(len(i) for i in items)
        for lst in items:
            if len(lst) < maxlen:
                lst.extend((('', ''),)*(maxlen-len(lst)))

        return [i+('',)+j+(('',)*2)+k for i, j, k in zip(*items)]
