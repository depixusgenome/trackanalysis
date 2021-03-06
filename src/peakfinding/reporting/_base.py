#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines basic hybridstat related report objects and functions
"""
from typing                 import (
    Iterator, Optional, Sequence,  Dict, Tuple, List, TYPE_CHECKING
)
from abc                    import abstractmethod

import numpy as np

from excelreports.creation  import Reporter as _Reporter, column_method, FILEOBJ
from utils                  import initdefaults
if TYPE_CHECKING:
    from data.track         import Track
    from ..peaksarray       import Output as PeakOutput

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

        self._pos    = tuple(peaks.columnindex(u'Peak Position',
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

    def __call__(self, outp:Tuple['PeakOutput']):
        "returns a chart for this bead if peak is peaks zero"
        chart = self._parent.book.add_chart(dict(type = 'scatter'))
        size  = len(outp)
        self._rseries = self._args(size, 'square', 'blue')

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
    uncertainties: Dict[int, float] = {}
    durations:     Sequence[int]    = []
    def __init__(self, track: Optional['Track']) -> None:
        if track is not None:
            self.path          = track.path
            self.framerate     = track.framerate
            self.ncycles       = track.ncycles
            self.durations     = track.phase.duration(..., 'measure')
            self.uncertainties = dict(track.rawprecision(...))

class ReporterInfo:
    u"All info relevant to the current analysis report"
    errs:        List[Tuple[int, Exception]]           = []
    beads:       List[Tuple[int, Tuple['PeakOutput']]] = []
    minduration: int                                   = 1
    track:       TrackInfo                             = TrackInfo(None)

    @initdefaults(frozenset(locals()),
                  track = lambda obj, val: setattr(obj, 'track', TrackInfo(val)),
                  beads = lambda obj, val: obj.setbeads(val))
    def __init__(self, **_):
        pass

    def setbeads(self, beads):
        "sets the beads"
        if hasattr(beads, 'keys'):
            tmp   = beads
            beads = []
            for i in tmp.keys():
                try:
                    j = tmp[i]
                    beads.append((i, tuple(j) if isinstance(j, Iterator) else j))
                except Exception as exc: # pylint: disable=broad-except
                    beads.append((i, exc))
        else:
            beads  = list(beads)
        self.beads = [i for i in beads if not isinstance(i[1], Exception)]
        self.errs  = [i for i in beads if isinstance(i[1], Exception)]

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
        self.config:   ReporterInfo = cnf
        self.charting: ChartCreator = ChartCreator(self)

    def uncertainty(self, bead:int):
        u"returns uncertainties for all beads"
        return self.config.track.uncertainties[bead]

    def uncertainties(self):
        u"returns uncertainties for all beads"
        fcn = self.config.track.uncertainties.__getitem__
        return np.array([fcn(bead)*bead.distance.stretch
                         for bead, _ in self.config.beads],
                        dtype = 'f4')

    @staticmethod
    @column_method(u"Bead")
    def _beadid(bead:int, *_) -> int:
        u"bead id"
        return bead

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"
