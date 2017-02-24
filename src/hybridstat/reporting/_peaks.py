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
from ._base                 import (Peak, Key, Bead, Base,
                                    ChartCreator, sheettype, isref)

class _Neighbours: # pylint: disable=too-many-instance-attributes
    u"Peak bases and neighbours"
    _NEI = 3
    def __init__(self, base:Base) -> None:
        self._pins = iter(base.hpins)
        self._ref  = None # type: Key
        self._hpin = None # type: str
        self._sz   = max(len(x) for x in base.oligos)
        self._pos  = frozenset(base.oligos)
        self._haslengthpeak = base.haslengthpeak

        trans      = str.maketrans('atgc', 'tacg')
        self._neg  = frozenset(oli.translate(trans)[::-1] for oli in base.oligos) \
                   - self._pos
        self._all  = self._neg | self._pos

    def _compute(self, ref:Key, bead:Bead, peak:Peak):
        u"Peak bases and neighbours"
        if ref != self._ref:
            self._hpin = next(self._pins).value
            self._ref  = ref
        if peak.ref is not None:
            i = peak.ref
        else:
            dist = bead.distance
            i    = peak.pos.x * dist.stretch + dist.bias

        return int(floor(i-.5)) # -.5 because i starts at 1

    def _get(self, tot, oli):
        loli = -len(oli)-self._NEI
        return tot[loli-self._NEI:loli] + oli.upper() + tot[-self._NEI:]

    def neighbours(self, ref:Key, bead:Bead, peak:Peak) -> Optional[str]:
        u"Peak bases and neighbours"
        if peak is bead.peaks[0] or (self._haslengthpeak and peak is bead.peaks[-1]):
            return None
        ind = max(0, self._compute(ref, bead, peak)-self._sz)
        tot = self._hpin[ind-self._NEI:ind+self._sz+self._NEI]
        val = tot[:-self._NEI]

        oli = next((oli for oli in self._all if val.endswith(oli)), None)
        return tot if oli is None else self._get(tot, oli)

    def orientation(self, ref:Key, bead:Bead, peak:Peak) -> Optional[bool]:
        u"Oligo Orientation"
        if peak is bead.peaks[0] or (self._haslengthpeak and peak is bead.peaks[-1]):
            return None
        ind = max(0, self._compute(ref, bead, peak)-self._sz)
        val = self._hpin[ind:ind+self._sz]
        pos = sum(1 if val.endswith(oli) else 0 for oli in self._pos)
        neg = sum(1 if val.endswith(oli) else 0 for oli in self._neg)
        if pos == 0 and neg == 0:
            return None
        else:
            return pos >= neg

class _PositionInRef:
    def __init__(self, peaks:Base, peakcols: Columns) -> None:
        summ          = sheettype('summary')(peaks)
        self._isxlsx  = peaks.isxlsx()
        self._peakrow = 1+peaks.tablerow()
        self._beadrow = 1+summ.tablerow()
        self._oldbead = None                # type: Optional[Bead]
        self._haslengthpeak = peaks.haslengthpeak

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

    def position(self, ref:Key, bead:Bead, peak:Peak):
        u"computes a formula for that peak"
        if self._isxlsx:
            self._peakrow += 1
            if bead != self._oldbead:
                self._oldbead  = bead
                self._beadrow += 1
            if bead.key != ref:
                return self._posfmt.format(self._peakrow, self._beadrow, self._beadrow)

        dist = bead.distance
        return peak.pos.x*dist.stretch+dist.bias

    def distance(self, ref:Key, bead:Bead, peak:Peak):
        u"computes distance to that peak"
        if bead.key == ref:
            return None
        if peak is bead.peaks[0] or (self._haslengthpeak and peak is bead.peaks[-1]):
            return None
        elif self._isxlsx:
            return self._disfmt.format(self._peakrow, self._peakrow, self._peakrow)
        elif peak.ref is not None:
            dist = bead.distance
            return peak.ref-(peak.pos.x*dist.stretch+dist.bias)

@sheet_class(u"Peaks")
class PeaksSheet(Base):
    u"Creates peaks sheet"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._neig = None
        self._pos  = None
        self._charting = ChartCreator(self, lambda bead: min(10,len(bead.peaks)))

    def iterate(self) -> 'Iterator[Tuple[Key,Bead,Peak]]':
        u"Iterates through peaks of each bead"
        for k, bead in self.beads():
            for peak in bead.peaks:
                yield k, bead, peak

    def linemark(self, info) -> bool: # pylint: disable=no-self-use
        u"group id (medoid, a.k.a central bead id)"
        return info[1].peaks[0] is info[2]

    def _disttoref_conditional(self):
        if len(self.hpins):
            sigmas = iter(bead.uncertainty*bead.distance.stretch for _, bead in self.beads())
            sigmas = np.fromiter(sigmas, dtype = 'f4')
        else:
            sigmas = np.fromiter((bead.uncertainty for _, bead in self.beads()),
                                 dtype = 'f4')
        sigma  = np.median(sigmas)

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

    def _prob_median(self, name:str, ref:Key, bead:Bead, peak:Peak):
        if peak is bead.peaks[0] or (self.haslengthpeak and peak is bead.peaks[-1]):
            return None
        elif isref(bead):
            ite = iter(pk.prob            for _, pk in self.peaks(ref, peak.pos.x))
            ite = iter(getattr(prob,name) for prob  in ite if prob is not None)
            arr = np.fromiter(ite, np.float32)
            if len(arr) == 0:
                return None
            return np.median(arr)
        else:
            return None if peak.prob is None else getattr(peak.prob, name)

    def columns(self):
        u"list of columns in table"
        cols       = super().columns()
        self._pos  = _PositionInRef(self, cols)
        self._neig = None if self.nohairpin() else _Neighbours(self)
        return cols

    @staticmethod
    @column_method(u"Bead")
    def _beadid(_, bead:Bead, _2) -> str:
        u"Bead id"
        return str(bead.key)

    @staticmethod
    @column_method(u"Reference")
    def _refid(ref:Key, *_) -> str:
        u"Group id (medoid, a.k.a central bead id)"
        return str(ref)

    @staticmethod
    @column_method(u"Reference Peak", units = Base.baseunits, fmt = int)
    def _refpos(_, bead:Bead, peak:Peak) -> Optional[float]:
        u"Position of the same peak in the reference (if found)"
        if peak is bead.peaks[0]:
            return 0
        return peak.ref

    @column_method(u"Peak Position in Reference",
                   units = Base.baseunits,
                   fmt   = Base.basefmt)
    def _peakref(self, *args) -> Optional[float]:
        u"Position of the peak in the reference's frame"
        return self._pos.position(*args)

    @column_method(u"Distance to Reference",
                   units = Base.baseunits,
                   cond  = _disttoref_conditional,
                   fmt   = Base.basefmt)
    def _disttoref(self, ref:Key, bead:Bead, peak:Peak) -> Optional[str]:
        u"Difference: reference peak position minus the bead's peak position"
        return self._pos.distance(ref, bead, peak)

    @staticmethod
    @column_method(u"Peak Position")
    def _peakpos(_1, _2, peak:Peak) -> float:
        u"Peak position as measured (µm)"
        return peak.pos.x

    @column_method(u"Peak Height")
    def _nevt(self, ref:Key, bead:Bead, peak:Peak) -> int:
        u"""
        Number of hybridizations in that peak.

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        if peak is bead.peaks[0] or (self.haslengthpeak and peak is bead.peaks[-1]):
            return None
        elif isref(bead):
            ite = iter(len(pk.events) for _, pk in self.peaks(ref, peak.pos.x))
            arr = np.fromiter(ite, np.int32)
            if len(arr) == 0:
                return 0
            return np.median(arr)
        else:
            return len(peak.events)

    @column_method(u"Neighbours", exclude = Base.nohairpin)
    def _neighbours(self, *args) -> Optional[str]:
        return self._neig.neighbours(*args)

    @column_method(u"Orientation", exclude = Base.nohairpin)
    def _orientation(self, *args) -> Optional[bool]:
        return self._neig.orientation(*args)

    @column_method(u"Hybridisation Rate")
    def _hrate(self, ref:Key, bead:Bead, peak:Peak) -> Optional[float]:
        u"""
        Peak height divided by number of cycles.

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        if peak is bead.peaks[0] or (self.haslengthpeak and peak is bead.peaks[-1]):
            return 0.
        elif isref(bead):
            ite = iter(len(pk.events)/bd.ncycles for bd, pk in self.peaks(ref, peak.pos.x))
            arr = np.fromiter(ite, np.float32)
            if len(arr) == 0:
                return 0
            return np.median(arr)
        else:
            return len(peak.events)/bead.ncycles

    @column_method(u"Hybridisation Time", units = 'seconds')
    def _time(self, *args) -> Optional[float]:
        u"""
        Average time to de-hybridization, for a frame rate of 30Hz.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._prob_median('time', *args)

    @column_method(u"Hybridisation Time Probability")
    def _prob(self, *args) -> Optional[float]:
        u"""
        Probability to de-hybridize between 2 time frames.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._prob_median('probability', *args)

    @column_method(u"Hybridisation Time Uncertainty", units = 'seconds')
    def _uncert(self, *args) -> Optional[float]:
        u"""
        1-sigma uncertainty on the de-hybridization time:
            UNCERTAINTY ~ TIME / sqrt(NUMBER OF HYBRIDISATIONS)

        For a hairpin, this is set to the median of values
        found in its group for that peak.
        """
        return self._prob_median('uncertainty', *args)

    @column_method(u"", exclude = lambda x: not x.isxlsx())
    def _chart(self, *args):
        return self._charting.peaks(*args)
