#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates peaks sheet
"""
from typing                 import Tuple, Iterator, Optional # pylint: disable=unused-import
from math                   import floor
from xlsxwriter.utility     import xl_col_to_name

import numpy as np

from excelreports.creation  import column_method, sheet_class, Columns
from data.trackitems        import BEADKEY                   # pylint: disable=unused-import
from ..probabilities        import Probability
from ._base                 import Reporter, HasLengthPeak, Group, Bead

class Probabilities(HasLengthPeak):
    u"Computes and caches probabilities"
    def __init__(self, base:Reporter) -> None:
        super().__init__(base)
        self._proba  = Probability(framerate = base.track.frequency)
        self._values = dict()   # type: Dict[Tuple[BEADKEY,int], Probability]

    def __cache(self, bead:Bead, ipk:int) -> Probability:
        if self._isstructural(bead, ipk):
            return None

        key = (bead.key, ipk)
        val = self._values.get(key, None)
        if val is not None:
            return val

        self._values[key] = val = self._proba(bead.events[ipk][1])
        return val

    def __call__(self, name: str, group:Group, bead:Bead, ipk:int):
        u"returns a probability value for a bead or the median for a hairpin"
        if self._isstructural(bead, ipk):
            return None
        elif bead is None:
            pkkey = bead.peaks[0]
            ite = iter(self.__cache(i, j)
                       for i in group.beads for j in range(len(i.peaks))
                       if i.peaks[j][1] == pkkey)
            ite = iter(getattr(prob,name) for prob  in ite if prob is not None)
            arr = np.array([getattr(i, name) for i in ite], dtype = 'f4')
            if len(arr) == 0:
                return None
            return np.median(arr)
        else:
            return getattr(self._values[(bead.key, ipk)], name)

class Neighbours(HasLengthPeak):
    u"Peak bases and neighbours"
    _NEI = 3
    def __init__(self, base:Reporter) -> None:
        super().__init__(base)
        self._pins     = base.sequences
        self._oldbead  = (None, None)   # type: Tuple[Optional[Group], Optional[Bead]]
        self._hpin     = None           # type: str
        self._sz       = max(len(x) for x in base.oligos)
        self._pos      = frozenset(base.oligos)

        trans      = str.maketrans('atgc', 'tacg')
        self._neg  = frozenset(oli.translate(trans)[::-1] for oli in base.oligos) \
                   - self._pos
        self._all  = self._neg | self._pos

    def __compute(self, ref:Group, bead:Bead, ipk:int):
        u"Peak bases and neighbours"
        if ref is not self._oldbead[0] or bead is not self._oldbead[1]:
            self._hpin    = self._pins[ref.key]
            self._oldbead = (ref, bead)

        if np.isnan(bead.peaks[ipk][1]):
            i = self._basevalue(bead, ipk)
        else:
            i = bead.peaks[ipk][1]

        return int(floor(i+.5))

    def __get(self, tot, oli):
        loli = -len(oli)-self._NEI
        return tot[loli-self._NEI:loli] + oli.upper() + tot[-self._NEI:]

    def neighbours(self, ref:Group, bead:Bead, ipk:int) -> Optional[str]:
        u"Peak bases and neighbours"
        if self._isstructural(bead, ipk):
            return None

        ind = max(0, self.__compute(ref, bead, ipk)-self._sz)
        tot = self._hpin[ind-self._NEI:ind+self._sz+self._NEI]
        val = tot[:-self._NEI]

        oli = next((oli for oli in self._all if val.endswith(oli)), None)
        return tot if oli is None else self.__get(tot, oli)

    def orientation(self, ref:Group, bead:Bead, ipk:int) -> Optional[bool]:
        u"Oligo Orientation"
        if self._isstructural(bead, ipk):
            return None

        ind = max(0, self.__compute(ref, bead, ipk)-self._sz)
        val = self._hpin[ind:ind+self._sz]
        pos = sum(1 if val.endswith(oli) else 0 for oli in self._pos)
        neg = sum(1 if val.endswith(oli) else 0 for oli in self._neg)
        if pos == 0 and neg == 0:
            return None
        else:
            return pos >= neg

class PositionInRef(HasLengthPeak):
    u"Deals with positions"
    def __init__(self, peaks:Reporter, peakcols: Columns) -> None:
        super().__init__(peaks)
        summ          = peaks.sheettype('summary')(peaks)
        self._isxlsx  = peaks.isxlsx()
        self._peakrow = 1+peaks.tablerow()
        self._beadrow = 1+summ.tablerow()
        self._oldbead = None                # type: Optional[Tuple[Group, Bead]]

        def _cell(name):
            for i, col in enumerate(summ.columns()):
                if summ.columnname(col) == name:
                    return u'INDIRECT("{}!{}'.format(summ.sheet_name,
                                                     xl_col_to_name(i))+u'{}") '
            raise KeyError("Missing column")

        def _colname(name):
            filt = iter(peaks.columnname(col) for col in peakcols)
            filt = iter(i for i, col in enumerate(filt) if col == name)
            return xl_col_to_name(next(filt))+u"{}"

        peak = _colname(u'Peak Position')
        self._posfmt  = u"= {} * {} + {}".format(peak, _cell(u"Stretch"), _cell(u"Bias"))

        peak = _colname(u'Peak Position in Reference')
        ref  = _colname(u'Reference Peak')
        self._disfmt  = u'=IF(ISBLANK({0}), "", {0} - {1})'.format(ref, peak)

    def position(self, ref:Group, bead:Bead, ipk:int):
        u"computes a formula for that peak"
        if self._isxlsx:
            self._peakrow += 1
            if ref is not self._oldbead[0] or bead is not self._oldbead[1]:
                self._oldbead  = ref, bead
                self._beadrow += 1
            if bead is not None:
                return self._posfmt.format(self._peakrow, self._beadrow, self._beadrow)

        return self._basevalue(bead, ipk)

    def distance(self, _, bead:Bead, ipk:int):
        u"computes distance to that peak"
        if bead is None or self._isstructural(bead, ipk):
            return None
        elif self._isxlsx:
            return self._disfmt.format(self._peakrow, self._peakrow, self._peakrow)
        else:
            key = bead.peaks[ipk][1]
            if np.isfinite(key):
                return key - self._basevalue(bead, ipk)

@sheet_class(u"Peaks")
class PeaksSheet(Reporter, HasLengthPeak):
    u"Creates peaks sheet"
    _MINCHARTHEIGHT = 10
    def __init__(self, *args, **kwargs):
        super().__init__(*args, height = lambda bead: min(10, len(bead.peaks)), **kwargs)
        self._neig  = None
        self._pos   = None
        self._proba = Probabilities(self)

    @classmethod
    def chartheight(cls, bead:Bead) -> int:
        u"Returns the chart height"
        return min(cls._MINCHARTHEIGHT, len(bead.peaks))

    def iterate(self) -> Iterator[Tuple[Group, Bead, int]]:
        u"Iterates through peaks of each bead"
        for group in self.groups():
            hpin = self.hpins[group.key]
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
        u"list of columns in table"
        cols       = super().columns()
        self._pos  = PositionInRef(self, cols)
        self._neig = None if self.nohairpin() else Neighbours(self)
        return cols

    @column_method(u"Reference Peak", units = Reporter.baseunits, fmt = int)
    def _refpos(self, ref:Group, bead:Bead, ipk:int) -> Optional[float]:
        u"Position of the same peak in the reference (if found)"
        if ipk == 0:
            return 0
        if bead is None:
            return self.hpins[ref.key].peaks[ipk]
        else:
            val = bead.peaks[ipk][1]
            return val if np.isfinite(val) else None

    @column_method(u"Peak Position in Reference",
                   units = Reporter.baseunits,
                   fmt   = Reporter.basefmt)
    def _peakref(self, *args) -> Optional[float]:
        u"Position of the peak in the reference's frame"
        return self._pos.position(*args)

    @column_method(u"Distance to Reference",
                   units = Reporter.baseunits,
                   cond  = _disttoref_conditional,
                   fmt   = Reporter.basefmt)
    def _disttoref(self, *args) -> Optional[str]:
        u"Difference: reference peak position minus the bead's peak position"
        return self._pos.distance(*args)

    @staticmethod
    @column_method(u"Peak Position")
    def _peakpos(_, bead:Bead, ipk:int) -> float:
        u"Peak position as measured (µm)"
        return bead.peaks[ipk][0]

    @column_method(u"Peak Height")
    def _nevt(self, ref:Group, bead:Bead, ipk:int) -> int:
        u"""
        Number of hybridizations in that peak.

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('nevents', ref, bead, ipk)

    @column_method(u"Neighbours", exclude = Reporter.nohairpin)
    def _neighbours(self, *args) -> Optional[str]:
        return self._neig.neighbours(*args)

    @column_method(u"Orientation", exclude = Reporter.nohairpin)
    def _orientation(self, *args) -> Optional[bool]:
        return self._neig.orientation(*args)

    @column_method(u"Hybridisation Rate")
    def _hrate(self, *args) -> Optional[float]:
        u"""
        Peak height divided by number of cycles.

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('nevents', *args)/self.track.ncycles

    @column_method(u"Hybridisation Time", units = 'seconds')
    def _averageduration(self, *args) -> Optional[float]:
        u"""
        Average time to de-hybridization, for a frame rate of 30Hz.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('averageduration', *args)

    @column_method(u"Hybridisation Time Probability")
    def _prob(self, *args) -> Optional[float]:
        u"""
        Probability to de-hybridize between 2 time frames.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('probability', *args)

    @column_method(u"Hybridisation Time Uncertainty", units = 'seconds')
    def _uncert(self, *args) -> Optional[float]:
        u"""
        1-sigma uncertainty on the de-hybridization time:
            UNCERTAINTY ~ TIME / sqrt(NUMBER OF HYBRIDISATIONS)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._proba('uncertainty', *args)

    @column_method(u"", exclude = lambda x: not x.isxlsx())
    def _chart(self, ref:Group, bead:Bead, ipk:int):
        if ipk == 0:
            return self.charting(ref, bead)
