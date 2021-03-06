#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines basic hybridstat related report objects and functions
"""
from typing                 import Optional, Sequence, Dict, List, Tuple, Iterator
from abc                    import abstractmethod

import numpy as np

from excelreports.creation  import Reporter as _Reporter, column_method, FILEOBJ
from data.track             import Track
from sequences              import read as readsequence
from peakcalling.tohairpin  import HairpinFitter
from peakcalling.processor  import ByHairpinGroup as Group, ByHairpinBead as Bead
from taskmodel              import PHASE
from utils                  import initdefaults

class HasLengthPeak:
    "Deals with the number of peaks"
    def __init__(self, base:'HasLengthPeak') -> None:
        self.haslengthpeak                   = getattr(base, 'haslengthpeak', False)
        self.hairpins: Dict[str, HairpinFitter] = getattr(base, 'hairpins', {})

    def isstructural(self, ref:Group, bead:Bead, ipk:int) -> bool:
        "not peak 0 or size of hairpin"
        if ipk == 0:
            return True

        if bead is None:
            if ref.key not in self.hairpins:
                return True
            return len(self.hairpins[ref.key].peaks) == ipk+1

        return ipk == 0 or (self.haslengthpeak and ipk == len(bead.peaks)-1)

    @staticmethod
    def basevalue(bead, ipk):
        "converts zvalues to base values"
        dist = bead.distance
        return (bead.peaks[ipk][0]-dist.bias) * dist.stretch

class ChartCreator:
    "Creates charts"
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
        self._rseries: Optional[Dict] = None
        self._row    = peaks.tablerow()+1
        self._sheet  = peakstype.sheet_name

    def _args(self, nrows:int, tpe:str, color:str) -> dict:
        "return args for creating a chart"
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
            if ref.key not in self._parent.config.hairpins:
                return np.zeros(1, dtype = 'f4')
            return self._parent.config.hairpins[ref.key].peaks
        return bead.peaks['zvalue'] # type: ignore

    def __call__(self, ref:Group, bead:Bead):
        "returns a chart for this bead if peak is peaks zero"
        if ref.key is None:
            return None

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
    """
    All info in Track which is relevant to Reporter.
    This allows pickling ReporterInfo and producing reports later.
    """
    path                             = ''
    framerate                        = 0.
    ncycles                          = 0
    uncertainties:   Dict[int,float] = {}
    durations:       Sequence[int]   = []
    def __init__(self, track: Optional[Track]) -> None:
        if track is not None:
            self.path          = str(track.path)
            self.framerate     = track.framerate
            self.ncycles       = track.ncycles
            self.durations     = track.phase.duration(..., PHASE.measure)
            self.uncertainties = dict(track.rawprecision(...))

class ReporterInfo(HasLengthPeak):
    "All info relevant to the current analysis report"
    groups:     Sequence[Group]             = []
    errs:       List[Tuple[int, Exception]] = []
    hairpins:   Dict[str, HairpinFitter]    = {}
    sequences:  Dict[str, str]              = {}
    oligos:     Sequence[str]               = []
    knownbeads: Sequence[int]               = []
    minduration                             = 1
    haslengthpeak                           = False
    track                                   = TrackInfo(None)
    @initdefaults(frozenset(locals()))
    def __init__(self, *args:dict, **_) -> None:
        kwa = args[0] # initdefaults will have set args to [kwargs]

        if isinstance(kwa['groups'], Iterator):
            kwa['groups'] = list(kwa['groups'])

        elif callable(getattr(kwa['groups'], 'values', None)):
            kwa['groups'] = list(getattr(kwa['groups'], 'values')()) # type: ignore

        if isinstance(kwa['sequences'], str):
            kwa['sequences'] = dict(readsequence(kwa['sequences']))
        kwa['sequences'] = {i: j.lower() for i, j in kwa['sequences'].items()}

        if kwa.get('hairpins', None) is None:
            kwa['hairpins'] = dict(HairpinFitter.read(kwa['sequences'], kwa['oligos']))

        if kwa.get('knownbeads', None) is None:
            kwa.pop('knownbeads')

        kwa['track']  = TrackInfo(kwa['track'])
        kwa['errs']   = list(
            next((i.beads for i in kwa['groups'] if isinstance(i.beads, dict)), {})
            .items()
        )
        kwa['groups'] = [i for i in kwa['groups'] if not isinstance(i.beads, dict)]
        super().__init__(self)

    @staticmethod
    def sheettype(name:str):
        "Returns the columns associated with another sheet"
        for cls in Reporter.__subclasses__():
            if cls.__name__.lower() in (name.lower(), name.lower()+'sheet'):
                return cls
        raise KeyError('No sheet with name: '+name, "warning")

class Reporter(_Reporter):
    "Basic class for iterating over the data"
    def __init__(self, book: FILEOBJ, cnf: ReporterInfo) -> None:
        super().__init__(book)
        self.config   = cnf
        self.charting = ChartCreator(self)

    def baseunits(self)-> str:
        "Returns the unit value for bases"
        return u"µm" if self.nohairpin() else u"base"

    def basefmt(self)-> type:
        "Returns the format type for bases"
        return float if self.nohairpin() else int

    def nohairpin(self)-> bool:
        "returns true if no hairpin was provided"
        return len(self.config.hairpins) == 0

    def uncertainty(self, bead:Bead):
        "returns uncertainties for all beads"
        return self.config.track.uncertainties[bead.key]

    def uncertainties(self):
        "returns uncertainties for all beads"
        fcn = self.config.track.uncertainties.__getitem__
        return np.array([fcn(bead.key)*bead.distance.stretch
                         for group in self.config.groups
                         for bead  in group.beads],
                        dtype = 'f4')

    def beadncycles(self, bead:Bead) -> int:
        "returns the number of cycles for this bead"
        ncyc = self.config.track.ncycles
        if bead is not None:
            ncyc -= getattr(bead.events, 'discarded', 0)
        return ncyc

    @staticmethod
    @column_method(u"Bead")
    def _beadid(ref:Group, bead:Bead, *_) -> str:
        "bead id"
        return str((ref if bead is None else bead).key)

    @staticmethod
    @column_method(u"Reference")
    def _refid(ref:Group, *_) -> str:
        "group id (medoid, a.k.a central bead id)"
        return str(ref.key)

    @abstractmethod
    def iterate(self):
        "Iterates through sheet's base objects and their hierarchy"

    @staticmethod
    @abstractmethod
    def chartheight(npeaks:int) -> int:
        "Returns the chart height"
        return 1

    @staticmethod
    def linemark(info) -> bool:
        "marks a line"
        return not bool(info[-1])
