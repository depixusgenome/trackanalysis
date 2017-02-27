#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines basic hybridstat related report objects and functions
"""
from typing                 import Sequence, Callable, Dict # pylint:disable= unused-import
from abc                    import abstractmethod

import numpy as np

from excelreports.creation  import (Reporter as _Reporter,
                                    column_method, FILENAME, FILEOBJ, fileobj, Columns)
from data.track             import Track
from signalfilter           import PrecisionAlg
from peakcalling.tohairpin  import Hairpin                   # pylint: disable=unused-import
from peakcalling.processor  import (ByHairpinGroup as Group, # pylint: disable=unused-import
                                    ByHairpinBead  as Bead,
                                    Distance)

class HasLengthPeak:
    u"Deals with the number of peaks"
    _haslengthpeak = False
    def __init__(self, base:'HasLengthPeak') -> None:
        self._haslengthpeak = getattr(base, 'haslengthpeak', False)

    def _isstructural(self, bead:Bead, ipk:int) -> bool:
        return ipk == 0 or (self._haslengthpeak and ipk == len(bead.peaks)-1)

    @staticmethod
    def _basevalue(bead, ipk):
        dist = bead.distance
        return bead.peaks[ipk][0] * dist.stretch + dist.bias

class ChartCreator(object):
    u"Creates charts"
    _ERR    = .015
    _WIDTH  = 400
    _HUNIT  = 18
    def __init__(self, parent : 'Reporter') -> None:
        peakstype = parent.sheettype('peaks')
        peaks     = parent if isinstance(parent, peakstype) else peakstype(parent)

        self._pos    = tuple(peaks.columnindex(u'Peak Position in Reference',
                                               u'Hybridisation Rate'))
        self._book   = parent.book
        self._height = parent.chartheight
        self._rseries= None      # type: dict
        self._row    = peaks.tablerow()+1
        self._sheet  = peakstype.sheet_name

    def _args(self, nrows:int, tpe:str, color:str) -> dict:
        u"return args for creating a chart"
        def _pos(i):
            return [self._sheet, self._row, self._pos[i], self._row+nrows-1, self._pos[i]]
        return dict(name         = [self._sheet, self._row, 0],
                    categories   = _pos(0),
                    values       = _pos(1),
                    marker       = dict(type  = tpe,
                                        #size  = 0.1,
                                        fill  = dict(color = color)),
                    x_error_bars = dict(type  = 'fixed',
                                        value = self._ERR,
                                        line  = dict(color = color)))

    def __call__(self, ref:Group, bead:Bead):
        u"returns a chart for this bead if peak is peaks zero"
        chart = self._book.add_chart(dict(type = 'scatter'))

        if bead is None:
            self._rseries = self._args(len(bead.peaks), 'square', 'blue')
        else:
            series = self._args(len(bead.peaks), 'circle', 'green')
            chart.add_series(series)

        chart.add_series(self._rseries)
        chart.set_title (dict(none  = True))
        chart.set_legend(dict(none  = True))
        axis = dict(major_gridlines = dict(visible = False),
                    label_position  = "none",
                    visible         = True)
        chart.set_x_axis(axis)
        chart.set_y_axis(axis)
        chart.set_size  (dict(width  = self._WIDTH,
                              height = self._HUNIT*self._height(bead)))
        self._row += len(bead.peaks)
        return chart

class ReporterInfo(HasLengthPeak):
    u"All info relevant to the current analysis report"
    def __init__(self, arg = None, **kwargs):
        if isinstance(arg, ReporterInfo):
            for name in ('groups', 'hpins', 'oligos', 'config', 'track'):
                setattr(self, name, getattr(arg, name))
        else:
            self.track     = kwargs['track']
            self.groups    = kwargs['groups']       # type: Sequence[Group]
            self.hpins     = kwargs['hairpins']     # type: Dict[str, Hairpin]
            self.sequences = kwargs['sequences']    # type: Dict[str, str]
            self.oligos    = kwargs['oligos']       # type: Sequence[str]
        HasLengthPeak.__init__(self, arg)

    @staticmethod
    def sheettype(name:str):
        u"Returns the columns associated with another sheet"
        for cls in Reporter.__subclasses__():
            if cls.__name__.lower() in (name.lower(), name.lower()+'sheet'):
                return cls
        raise KeyError('No sheet with name: '+name)

    def sheetcolumns(self, name:str) -> Columns:
        u"Returns the columns associated with another sheet"
        return self.sheettype(name)(self).columns()

    def run(self, fname:FILENAME, **args):
        "creates a summary"
        with fileobj(fname) as book:
            summ = self.sheettype("summary")(book, self)

            summ.info(args['config'])
            summ.table ()

            self.sheettype("peak")(summ).table()

class Reporter(_Reporter):
    u"Basic class for iterating over the data"
    def __init__(self, book: FILEOBJ, cnf: ReporterInfo) -> None:
        super().__init__(book)
        self.config   = cnf
        self.charting = ChartCreator(self)

    @property
    def track(self) -> Track:
        u"The track being analyzed"
        return self.config.track

    @property
    def groups(self) -> Sequence[Group]:
        u"The groups that were found"
        return self.config.groups

    @property
    def hpins(self) -> Dict[str, Hairpin]:
        u"The hairpin peaks being analyzed"
        return self.config.hpins

    @property
    def sequences(self) -> Dict[str, str]:
        u"The hairpin peaks being analyzed"
        return self.config.sequences

    @property
    def oligos(self) -> Sequence[str]:
        u"The hairpin peaks being analyzed"
        return self.config.oligos

    @abstractmethod
    @staticmethod
    def chartheight(bead:Bead) -> int:
        u"Returns the chart height"
        return 1

    def baseunits(self)-> str:
        u"Returns the unit value for bases"
        return u"µm" if self.nohairpin() else u"base"

    def basefmt(self)-> type:
        u"Returns the format type for bases"
        return float if self.nohairpin() else int

    def nohairpin(self)-> bool:
        u"returns true if no hairpin was provided"
        return len(self.hpins) == 0

    @staticmethod
    @column_method(u"Bead")
    def _beadid(ref:Group, bead:Bead, *_) -> str:
        u"bead id"
        return str((ref if bead is None else bead).key)

    @staticmethod
    @column_method(u"Reference")
    def _refid(ref:Group, *_) -> str:
        u"group id (medoid, a.k.a central bead id)"
        return str(ref.key)

    def uncertainty(self, bead:Bead):
        u"returns uncertainties for all beads"
        return PrecisionAlg.rawprecision(self.track, bead.key)

    def uncertainties(self):
        u"returns uncertainties for all beads"
        fcn = self.uncertainty
        return np.array([fcn(bead.key)*bead.distance.stretch
                         for group in self.groups
                         for bead  in group.beads],
                        dtype = 'f4')

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

    @staticmethod
    def linemark(info) -> bool:
        u"marks a line"
        return not bool(info[-1])
