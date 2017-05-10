#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates peaks sheet
"""
from typing                 import (Tuple, Iterator,  # pylint: disable=unused-import
                                    Optional, Dict)
from math                   import floor
from xlsxwriter.utility     import xl_col_to_name

import numpy as np

from excelreports.creation  import column_method, sheet_class, Columns
from data.trackitems        import BEADKEY            # pylint: disable=unused-import
from ..probabilities        import Probability
from ._base                 import Reporter, HasLengthPeak, Group, Bead

class Probabilities(HasLengthPeak):
    "Computes and caches probabilities"
    def __init__(self, base:Reporter) -> None:
        super().__init__(base.config)
        self._proba  = Probability(framerate   = base.config.track.framerate,
                                   minduration = base.config.minduration)
        self._values = dict()   # type: Dict[Tuple[BEADKEY,int], Probability]
        self._ends   = base.config.track.durations

    def __cache(self, bead:Bead, ipk:int) -> Probability:
        key = (bead.key, ipk)
        val = self._values.get(key, None)
        if val is not None:
            return val

        self._values[key] = val = self._proba(bead.events[ipk][1], self._ends)
        return val

    def __call__(self, name: str, ref:Group, bead:Bead, ipk:int):
        "returns a probability value for a bead or the median for a hairpin"
        if bead is None:
            pkkey = np.int32(self.hairpins[ref.key].peaks[ipk]+.1) # type: ignore
            ite = iter(self.__cache(i, j)
                       for i in ref.beads for j in range(len(i.peaks))
                       if i.peaks['key'][j] == pkkey)
            arr = np.array([getattr(i, name) for i in ite], dtype = 'f4')
            if len(arr) == 0:
                return None
            return np.median(arr)
        else:
            return getattr(self.__cache(bead, ipk), name)

class Neighbours(HasLengthPeak):
    "Peak bases and neighbours"
    _NEI = 3
    def __init__(self, base:Reporter) -> None:
        super().__init__(base.config)
        self._seqs     = base.config.sequences
        self._oldbead  = (None, None)   # type: Tuple[Optional[Group], Optional[Bead]]
        self._sz       = max(len(x) for x in base.config.oligos)
        self._pos      = frozenset(base.config.oligos)

        trans      = str.maketrans('atgc', 'tacg')
        self._neg  = (frozenset(oli.translate(trans)[::-1] for oli in base.config.oligos)
                      - self._pos)
        self._all  = self._neg | self._pos

    def __compute(self, ref:Group, bead:Bead, ipk:int):
        "Peak bases and neighbours"
        if ref is not self._oldbead[0] or bead is not self._oldbead[1]:
            self._oldbead = (ref, bead)

        if bead is None:
            i = int(self.hairpins[ref.key].peaks[ipk]+1)
        elif bead.peaks['key'][ipk] < 0:
            i = int(floor(self.basevalue(bead, ipk)+1.5))
        else:
            i = bead.peaks['key'][ipk]+1

        return max(0, i-self._sz)

    def __get(self, tot, oli):
        loli = -len(oli)-self._NEI
        return tot[loli-self._NEI:loli] + oli.upper() + tot[-self._NEI:]

    def neighbours(self, ref:Group, bead:Bead, ipk:int) -> Optional[str]:
        "Peak bases and neighbours"
        if self.isstructural(ref, bead, ipk):
            return None

        ind = self.__compute(ref, bead, ipk)
        tot = self._seqs[ref.key][ind-self._NEI:ind+self._sz+self._NEI]
        val = tot[:-self._NEI]

        oli = next((oli for oli in self._all if val.endswith(oli)), None)
        return tot if oli is None else self.__get(tot, oli)

    def orientation(self, ref:Group, bead:Bead, ipk:int) -> Optional[bool]:
        "Oligo Orientation"
        if self.isstructural(ref, bead, ipk):
            return None

        ind = self.__compute(ref, bead, ipk)
        val = self._seqs[ref.key][ind:ind+self._sz]
        pos = sum(1 if val.endswith(oli) else 0 for oli in self._pos)
        neg = sum(1 if val.endswith(oli) else 0 for oli in self._neg)
        if pos == 0 and neg == 0:
            return None
        else:
            return pos >= neg

class PositionInRef(HasLengthPeak):
    "Deals with positions"
    def __init__(self, peaks:Reporter, peakcols: Columns) -> None:
        super().__init__(peaks)
        summ          = peaks.config.sheettype('summary')(peaks.book, peaks.config)
        self._hpins   = peaks.config.hairpins
        self._isxlsx  = peaks.isxlsx()
        self._peakrow = 1+peaks.tablerow()
        self._beadrow = 1+summ.tablerow()
        self._oldbead = None # type: Optional[Tuple[Group, Bead]]

        def _cell(name):
            for i, col in enumerate(summ.columns()):
                if summ.columnname(col) == name:
                    return 'INDIRECT("{}!{}'.format(summ.sheet_name,
                                                    xl_col_to_name(i))+'{}") '
            raise KeyError("Missing column", "warning")

        def _colname(name):
            filt = iter(peaks.columnname(col) for col in peakcols)
            filt = iter(i for i, col in enumerate(filt) if col == name)
            return xl_col_to_name(next(filt))+"{}"

        peak = _colname('Peak Position')
        self._posfmt  = "= ({}-{}) * {}".format(peak, _cell("Bias"), _cell("Stretch"))

        peak = _colname('Peak Position in Reference')
        ref  = _colname('Reference Peak')
        self._disfmt  = '=IF(ISBLANK({0}), "", {0} - {1})'.format(ref, peak)

    def position(self, ref:Group, bead:Bead, ipk:int):
        "computes a formula for that peak"
        if self._isxlsx:
            self._peakrow += 1
            if (ref, bead) != self._oldbead:
                self._oldbead  = ref, bead
                self._beadrow += 1
            if bead is not None:
                return self._posfmt.format(self._peakrow, self._beadrow, self._beadrow)

        if bead is None:
            return self._hpins[ref.key].peaks[ipk]
        else:
            return self.basevalue(bead, ipk)

    def distance(self, ref:Group, bead:Bead, ipk:int):
        "computes distance to that peak"
        if bead is None or self.isstructural(ref, bead, ipk):
            return None
        elif self._isxlsx:
            return self._disfmt.format(self._peakrow, self._peakrow, self._peakrow)
        else:
            key = bead.peaks['key'][ipk]
            if key >= 0:
                return key - self.basevalue(bead, ipk)

@sheet_class("Peaks")
class PeaksSheet(Reporter):
    "Creates peaks sheet"
    _MINCHARTHEIGHT = 10
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._neig  = None
        self._pos   = None
        self._proba = Probabilities(self)

    @classmethod
    def chartheight(cls, npeaks:int) -> int:
        "Returns the chart height"
        return min(cls._MINCHARTHEIGHT, npeaks)

    def iterate(self) -> Iterator[Tuple[Group, Bead, int]]:
        "Iterates through peaks of each bead"
        for group in self.config.groups:
            if group.key is None:
                continue

            hpin = self.config.hairpins[group.key]
            yield from ((group, None, i) for i in range(len(hpin.peaks)))
            for bead in group.beads:
                yield from ((group, bead, i) for i in range(len(bead.peaks)))

    def _disttoref_conditional(self):
        sigma  = np.median(self.uncertainties())

        def __get(fmt, val1, val2):
            val1 = val1*sigma
            if isinstance(val2, bool):
                ans  = dict( criteria =  '>'  if val2 else '<',
                             value    =  val1)
            else:
                val2 = val2*sigma
                ans  = dict( criteria = 'between',
                             minimum  = min(val1, val2),
                             maximum  = max(val1, val2))
            ans.update(dict(type = 'cell', format = fmt))
            return ans

        def _get(fmt, val1, val2 = None):
            fmt = self.book.add_format(dict(bg_color = fmt))
            return (__get(fmt,  val1, True  if val2 is None else  val2),
                    __get(fmt, -val1, False if val2 is None else -val2))

        return _get("#FFFFBF", 2.5, 5.)+_get("#FFC7CE", 5.)

    def columns(self) -> Columns:
        "list of columns in table"
        cols       = super().columns()
        self._pos  = PositionInRef(self, cols)
        self._neig = None if self.nohairpin() else Neighbours(self)
        return cols

    @column_method("Reference Peak", units = Reporter.baseunits, fmt = int)
    def _refpos(self, ref:Group, bead:Bead, ipk:int) -> Optional[float]:
        "Position of the same peak in the reference (if found)"
        if ipk == 0:
            return 0
        if bead is None:
            return self.config.hairpins[ref.key].peaks[ipk]
        else:
            val = bead.peaks['key'][ipk]
            return val if val >= 0 else None

    @column_method("Peak Position in Reference",
                   units = Reporter.baseunits,
                   fmt   = Reporter.basefmt)
    def _peakref(self, *args) -> Optional[float]:
        "Position of the peak in the reference's frame"
        return self._pos.position(*args)

    @column_method("Distance to Reference",
                   units = Reporter.baseunits,
                   cond  = _disttoref_conditional,
                   fmt   = Reporter.basefmt)
    def _disttoref(self, *args) -> Optional[float]:
        "Difference: reference peak position minus the bead's peak position"
        return self._pos.distance(*args)

    @staticmethod
    @column_method("Peak Position")
    def _peakpos(_, bead:Bead, ipk:int) -> float:
        "Peak position as measured (µm)"
        return None if bead is None else bead.peaks['zvalue'][ipk]

    @column_method("Peak Height")
    def _nevt(self, ref:Group, bead:Bead, ipk:int) -> int:
        """
        Number of hybridizations in that peak.

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('nevents', ref, bead, ipk)

    @column_method("Neighbours", exclude = Reporter.nohairpin)
    def _neighbours(self, *args) -> Optional[str]:
        return self._neig.neighbours(*args)

    @column_method("Orientation", exclude = Reporter.nohairpin)
    def _orientation(self, *args) -> Optional[bool]:
        return self._neig.orientation(*args)

    @column_method("Hybridisation Rate")
    def _hrate(self, *args) -> Optional[float]:
        """
        Peak height divided by number of cycles.

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        val = self._proba('nevents', *args)
        return 0. if val is None else val/self.config.track.ncycles

    @column_method("Hybridisation Time", units = 'seconds')
    def _averageduration(self, *args) -> Optional[float]:
        """
        Average time to de-hybridization, for a frame rate of 30Hz.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('averageduration', *args)

    @column_method("Hybridisation Time Probability")
    def _prob(self, *args) -> Optional[float]:
        """
        Probability to de-hybridize between 2 time frames.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('probability', *args)

    @column_method("Hybridisation Time Uncertainty", units = 'seconds')
    def _uncert(self, *args) -> Optional[float]:
        """
        1-sigma uncertainty on the de-hybridization time:
            UNCERTAINTY ~ TIME / sqrt(NUMBER OF HYBRIDISATIONS)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('uncertainty', *args)

    @column_method("", exclude = lambda x: not x.isxlsx())
    def _chart(self, ref:Group, bead:Bead, ipk:int):
        if ipk == 0:
            return self.charting(ref, bead)
