#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Defines basic hybridstat related report objects and functions
"""
from typing                 import (Optional, Sequence, # pylint:disable= unused-import
                                    Callable, Dict, Iterator, Tuple)
from abc                    import abstractmethod

import numpy as np

from utils                  import initdefaults
from model                  import PHASE
from excelreports.creation  import Reporter as _Reporter, column_method, FILEOBJ
from data.track             import Track, BEADKEY           # pylint: disable=unused-import
from signalfilter           import rawprecision
from ..selector             import Output as PeakOutput     # pylint: disable=unused-import

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
            self.durations     = track.phaseduration(..., PHASE.measure)
            self.uncertainties = dict(rawprecision(track, ...))

class ReporterInfo:
    u"All info relevant to the current analysis report"
    beads         = [] # type: Sequence[Tuple[BEADKEY, Tuple[PeakOutput]]]
    minduration   = 1
    track         = TrackInfo(None)
    @initdefaults(frozenset(locals()),
                  track = TrackInfo,
                  beads = lambda val: tuple((i, tuple(j)) for i, j in val))
    def __init__(self, **_):
        pass

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

    def uncertainty(self, bead:BEADKEY):
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
    def _beadid(bead:BEADKEY, *_) -> int:
        u"bead id"
        return bead

    @abstractmethod
    def iterate(self):
        u"Iterates through sheet's base objects and their hierarchy"

    @staticmethod
    def linemark(info) -> bool:
        u"marks a line"
        return not bool(info[-1])
