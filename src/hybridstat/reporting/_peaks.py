#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=no-value-for-parameter
"""
Creates peaks sheet
"""
from typing                 import Tuple, Iterator, Optional, Dict
from functools              import wraps
from math                   import floor
from xlsxwriter.utility     import xl_col_to_name

import numpy as np

from excelreports.creation      import column_method as _column_method, sheet_class, Columns
from peakfinding.probabilities  import Probability
from ._base                     import Reporter, HasLengthPeak, Group, Bead

@wraps(_column_method)
def column_method(*args, median = False, **kwa):
    "same as _column_method but adding some doc"
    meta  = _column_method(*args, **kwa)
    lines = ("For a hairpin, this is set to the median of values",
             "found in its group for that peak.")
    def _wrapper(fcn):
        if median:
            if fcn.__doc__ is None or fcn.__doc__.strip() == "":
                return meta(fcn)

            if fcn.__doc__[-1] != '\n':
                fcn.__doc__ += '\n'

            if "        " in fcn.__doc__:
                fcn.__doc__ += "\n"+"".join("        "+i+"\n" for i in lines)
            else:
                fcn.__doc__ += "\n"+"".join(i+"\n" for i in lines)
        return meta(fcn)
    return _wrapper

class Probabilities(HasLengthPeak):
    "Computes and caches probabilities"
    def __init__(self, base:Reporter) -> None:
        super().__init__(base.config)
        self._proba  = Probability(framerate   = base.config.track.framerate,
                                   minduration = base.config.minduration)
        self._values: Dict[Tuple[int,int], Probability] = dict()
        self._ends   = base.config.track.durations

    def __cache(self, bead:Bead, ipk:int) -> Probability:
        key = (bead.key, ipk)
        val = self._values.get(key, None)
        if val is None:
            evt = bead.events[ipk][1]  # type: ignore
            self._values[key] = tmp = self._proba(evt, self._ends)
            return tmp
        return val

    def array(self, name: str, ref:Group, ipk:int):
        "returns an array of values for this hairpin peak"
        if ref.key not in self.hairpins:
            return np.empty(0, dtype = 'f4')
        pkkey = np.int32(self.hairpins[ref.key].peaks[ipk]+.1) # type: ignore
        itr   = (self.__call__(name, None, i, j)
                 for i in ref.beads
                 for j in range(len(i.peaks))
                 if i.peaks['key'][j] == pkkey)
        return np.array([i for i in itr if i is not None], dtype = 'f4')

    def __call__(self, name: str, ref:Optional[Group], bead:Bead, ipk:int):
        "returns a probability value for a bead or the median for a hairpin"
        if bead is None:
            arr = self.array(name, ref, ipk)
            if len(arr) == 0:
                return None
            ret = np.median(arr)
            return ret if np.isfinite(ret) else None
        val = self.__cache(bead, ipk)
        if name == 'resolution' and name not in val.__dict__:
            # Per default, the resolution is not computed. We do it here
            if val.nevents == 0:
                setattr(val, name, None)
            else:
                evt = bead.events[ipk][1]  # type: ignore
                setattr(val, name, Probability.resolution(evt))

        return getattr(val, name)

class Neighbours(HasLengthPeak):
    "Peak bases and neighbours"
    _NEI = 3
    def __init__(self, base:Reporter) -> None:
        super().__init__(base.config)
        self._seqs     = base.config.sequences
        self._oldbead:  Tuple[Optional[Group], Optional[Bead]] = (None, None)
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
            if ref.key not in self.hairpins:
                return 0

            i = int(self.hairpins[ref.key].peaks[ipk])
        elif bead.peaks['key'][ipk] < 0:
            i = int(floor(self.basevalue(bead, ipk)+.5))
        else:
            i = bead.peaks['key'][ipk]

        return max(0, i-self._sz)

    def __get(self, tot, oli):
        loli = -len(oli)-self._NEI
        return tot[loli-self._NEI:loli] + oli.upper() + tot[-self._NEI:]

    def neighbours(self, ref:Group, bead:Bead, ipk:int) -> Optional[str]:
        "Peak bases and neighbours"
        if self.isstructural(ref, bead, ipk) or ref.key not in self._seqs:
            return None

        ind = self.__compute(ref, bead, ipk)
        tot = self._seqs[ref.key][ind-self._NEI:ind+self._sz+self._NEI]
        val = tot[:-self._NEI]

        oli = next((oli for oli in self._all if val.endswith(oli)), None)
        return tot if oli is None else self.__get(tot, oli)

    def orientation(self, ref:Group, bead:Bead, ipk:int) -> Optional[bool]:
        "Strand on which the oligo sticks"
        if self.isstructural(ref, bead, ipk) or ref.key not in self._seqs:
            return None

        ind = self.__compute(ref, bead, ipk)
        val = self._seqs[ref.key][ind:ind+self._sz]
        pos = sum(1 if val.endswith(oli) else 0 for oli in self._pos)
        neg = sum(1 if val.endswith(oli) else 0 for oli in self._neg)
        if pos == 0 and neg == 0:
            return None
        return pos >= neg

class PositionInRef(HasLengthPeak):
    "Deals with positions"
    def __init__(self, peaks:Reporter, peakcols: Columns) -> None:
        super().__init__(peaks) # type: ignore
        summ          = peaks.config.sheettype('summary')(peaks.book, peaks.config)
        self._hpins   = peaks.config.hairpins
        self._isxlsx  = peaks.isxlsx()
        self._peakrow = 1+peaks.tablerow()
        self._beadrow = summ.refrow()
        self._oldbead: Optional[Tuple[Group, Bead]] = None

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
            if ref.key not in self._hpins:
                return None
            return self._hpins[ref.key].peaks[ipk]
        return self.basevalue(bead, ipk)

    def distance(self, ref:Group, bead:Bead, ipk:int):
        "computes distance to that peak"
        if bead is None or self.isstructural(ref, bead, ipk):
            return None
        if self._isxlsx:
            return self._disfmt.format(self._peakrow, self._peakrow, self._peakrow)
        key = bead.peaks['key'][ipk]
        return key - self.basevalue(bead, ipk) if key >= 0 else None

@sheet_class("Peaks")
class PeaksSheet(Reporter):
    "Creates peaks sheet"
    _MINCHARTHEIGHT = 10
    _pos  : PositionInRef
    _neig : Optional[Neighbours]
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._proba = Probabilities(self)

    @classmethod
    def chartheight(cls, npeaks:int) -> int:
        "Returns the chart height"
        return min(cls._MINCHARTHEIGHT, npeaks)

    def iterate(self) -> Iterator[Tuple[Group, Optional[Bead], int]]:
        "Iterates through peaks of each bead"
        for group in self.config.groups:
            if group.key is None:
                continue

            if group.key in self.config.hairpins:
                hpin = self.config.hairpins[group.key]
                yield from ((group, None, i) for i in range(len(hpin.peaks)))
            else:
                yield (group, None, 0)

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
                    __get(fmt, -val1, False if val2 is None else -int(val2)))

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
            if ref.key not in self.config.hairpins:
                return None
            return self.config.hairpins[ref.key].peaks[ipk]
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
    def _peakpos(_, bead:Bead, ipk:int) -> Optional[float]:
        "Peak position as measured (µm)"
        return None if bead is None else bead.peaks['zvalue'][ipk]

    @column_method("σ[Peaks]", median = True, units = 'µm')
    def _peakresolution(self, *args) -> float:
        "Median deviation for event positions"
        return self._proba('resolution', *args)

    @column_method("Peak Height", median = True)
    def _nevt(self, ref:Group, bead:Bead, ipk:int) -> int:
        "Number of hybridisations in that peak."
        return self._proba('nevents', ref, bead, ipk)

    @column_method("Neighbours", exclude = Reporter.nohairpin)
    def _neighbours(self, *args) -> Optional[str]:
        return None if self._neig is None else self._neig.neighbours(*args)

    @column_method("Strand", exclude = Reporter.nohairpin)
    def _orientation(self, *args) -> Optional[bool]:
        "Strand on which the oligo sticks"
        return None if self._neig is None else self._neig.orientation(*args)

    @column_method("Hybridisation Rate", median = True)
    def _hrate(self, *args) -> Optional[float]:
        "Number of events divided by number of cycles."
        return self._proba('hybridisationrate', *args)

    @column_method("Hybridisation Time", units = 'seconds', median = True)
    def _averageduration(self, *args) -> Optional[float]:
        """
        Average time to de-hybridisation, for a frame rate of 30Hz.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)
        """
        return self._proba('averageduration', *args)

    @column_method("Hybridisation Time Probability", median = True)
    def _prob(self, *args) -> Optional[float]:
        """
        Probability to de-hybridize between 2 time frames.
        Note that: TIME = -1/(RATE * log(1.-PROBABILITY)
        """
        return self._proba('probability', *args)

    @column_method("Hybridisation Time Uncertainty", units = 'seconds', median = True)
    def _uncert(self, *args) -> Optional[float]:
        """
        1-sigma uncertainty on the de-hybridisation time:
            UNCERTAINTY ~ TIME / sqrt(NUMBER OF HYBRIDISATIONS)
        """
        return self._proba('uncertainty', *args)

    @column_method("", exclude = lambda x: not x.isxlsx())
    def _chart(self, ref:Group, bead:Bead, ipk:int):
        return self.charting(ref, bead) if ipk == 0 else None
