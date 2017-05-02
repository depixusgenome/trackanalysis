#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines basic hybridstat related report objects and functions
"""
from typing                 import (Optional, Sequence, # pylint:disable= unused-import
                                    Callable, Dict)
from abc                    import abstractmethod

import numpy as np

from utils                  import initdefaults
from model                  import PHASE
from excelreports.creation  import Reporter as _Reporter, column_method, FILEOBJ
from data.track             import Track, BEADKEY            # pylint: disable=unused-import
from signalfilter           import PrecisionAlg
from peakcalling.tohairpin  import Hairpin                   # pylint: disable=unused-import
from peakcalling.processor  import (ByHairpinGroup as Group, # pylint: disable=unused-import
                                    ByHairpinBead  as Bead,
                                    Distance)

class HasLengthPeak:
    u"Deals with the number of peaks"
    haslengthpeak = False
    def __init__(self, base:'HasLengthPeak') -> None:
        self.haslengthpeak = getattr(base, 'haslengthpeak', False)
        self.hairpins      = getattr(base, 'hairpins', {}) # type: Dict[str, Hairpin]

    def isstructural(self, ref:Group, bead:Bead, ipk:int) -> bool:
        u"not peak 0 or size of hairpin"
        if ipk == 0:
            return True

        if bead is None:
            return len(self.hairpins[ref.key].peaks) == ipk+1
        else:
            return ipk == 0 or (self.haslengthpeak and ipk == len(bead.peaks)-1)

    @staticmethod
    def basevalue(bead, ipk):
        u"converts zvalues to base values"
        dist = bead.distance
        return (bead.peaks[ipk][0]-dist.bias) * dist.stretch

class ChartCreator(object):
    u"Creates charts"
    _ERR    = .015
    _WIDTH  = 400
    _HUNIT  = 18
    def __init__(self, parent : 'Reporter') -> None:
        peakstype = parent.config.sheettype('peaks')
        if isinstance(parent, peakstype):
            peaks = parent
        else:
            peaks = peakstype(parent.book, parent.config)

        self._pos    = tuple(peaks.columnindex(u'Peak Position in Reference',
                                               u'Hybridisation Rate'))
        self._parent = parent
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

    def _peaks(self, ref:Group, bead:Bead):
        if bead is None:
            return self._parent.config.hairpins[ref.key].peaks
        else:
            return bead.peaks['zvalue']

    def __call__(self, ref:Group, bead:Bead):
        u"returns a chart for this bead if peak is peaks zero"
        if ref.key is None:
            return

        chart = self._parent.book.add_chart(dict(type = 'scatter'))
        size  = len(self._peaks(ref, bead))
        if bead is None:
            self._rseries = self._args(size, 'square', 'blue')
        else:
            series = self._args(size, 'circle', 'green')
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
                              height = self._HUNIT*self._parent.chartheight(size)))
        self._row += size
        return chart

class TrackInfo:
    u"""
    All info in Track which is relevant to Reporter.
    This allows pickling ReporterInfo and producing reports later.
    """
    path            = ''
    framerate       = 0.
    ncycles         = 0
    uncertainties   = {}    # type: Dict[BEADKEY,float]
    durations       = []    # type: Sequence[int]
    def __init__(self, track: Optional[Track]) -> None:
        if track is not None:
            self.path          = track.path
            self.framerate     = track.framerate
            self.ncycles       = track.ncycles
            self.durations     = track.phaseduration(...,PHASE.measure)
            self.uncertainties = {i: PrecisionAlg.rawprecision(track, i)
                                  for i in track.beads.keys()}

class ReporterInfo(HasLengthPeak):
    u"All info relevant to the current analysis report"
    groups      = [] # type: Sequence[Group]
    hairpins    = {} # type: Dict[str, Hairpin]
    sequences   = {} # type: Dict[str, str]
    oligos      = [] # type: Sequence[str]
    knownbeads  = [] # type: Sequence[BEADKEY]
    minduration = 1
    track       = TrackInfo(None)
    @initdefaults(frozenset(locals()) - {'track'})
    def __init__(self, **kwa):
        super().__init__(kwa)
        self.track = TrackInfo(kwa['track'])

    @staticmethod
    def sheettype(name:str):
        u"Returns the columns associated with another sheet"
        for cls in Reporter.__subclasses__():
            if cls.__name__.lower() in (name.lower(), name.lower()+'sheet'):
                return cls
        raise KeyError('No sheet with name: '+name, "warning")

class Reporter(_Reporter):
    u"Basic class for iterating over the data"
    def __init__(self, book: FILEOBJ, cnf: ReporterInfo) -> None:
        super().__init__(book)
        self.config   = cnf
        self.charting = ChartCreator(self)

    def baseunits(self)-> str:
        u"Returns the unit value for bases"
        return u"µm" if self.nohairpin() else u"base"

    def basefmt(self)-> type:
        u"Returns the format type for bases"
        return float if self.nohairpin() else int

    def nohairpin(self)-> bool:
        u"returns true if no hairpin was provided"
        return len(self.config.hairpins) == 0

    def uncertainty(self, bead:Bead):
        u"returns uncertainties for all beads"
        return self.config.track.uncertainties[bead.key]

    def uncertainties(self):
        u"returns uncertainties for all beads"
        fcn = self.config.track.uncertainties.__getitem__
        return np.array([fcn(bead.key)*bead.distance.stretch
                         for group in self.config.groups
                         for bead  in group.beads],
                        dtype = 'f4')

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

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

    @staticmethod
    @abstractmethod
    def chartheight(npeaks:int) -> int:
        u"Returns the chart height"
        return 1

    @staticmethod
    def linemark(info) -> bool:
        u"marks a line"
        return not bool(info[-1])
