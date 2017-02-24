#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates events sheet
"""
from typing                 import Tuple, Iterator, Optional
from excelreports.creation  import column_method, sheet_class
from ._base                 import Base, Position, Peak, Key, Bead

@sheet_class(u"Events")
class EventsSheet(Base):
    u"Creates events sheet"
    def iterate(self) -> Iterator[Tuple[Key,Bead,Peak,Position]]:
        u"Iterates through peaks of each bead"
        for k, bead in self.beads():
            for peak in bead.peaks:
                for evt in peak.events:
                    yield k, bead, peak, evt

    def linemark(self, info) -> bool:
        u"group id (medoid, a.k.a central bead id)"
        return info[1].peaks[0] is info[2] and info[2].events[0] == info[3]

    @staticmethod
    @column_method(u"Bead")
    def _beadid(_, bead:Bead, *_1) -> str:
        u"bead id"
        return str(bead.key)

    @staticmethod
    @column_method(u"Reference")
    def _refid(ref:Key, *_) -> str:
        u"group id (medoid, a.k.a central bead id)"
        return str(ref.key)

    @staticmethod
    @column_method(u"Reference Peak",
                   units = Base.baseunits,
                   fmt   = Base.basefmt)
    def _refpos(_1, _2, peak:Peak, _3) -> Optional[float]:
        u"Position of the same peak in the reference (if found)"
        return peak.ref

    @staticmethod
    @column_method(u"Peak Position", units = 'µm')
    def _peakpos(_1, _2, peak:Peak, _3) -> float:
        u"Peak position as measured"
        return peak.pos.x

    @staticmethod
    @column_method(u"Event Position")
    def _evtx(_1, _2, _3, evt:Position) -> float:
        u"Event position as measured for that bead (un-normalized)"
        return evt.x

    @staticmethod
    @column_method(u"Event Duration")
    def _evty(_1, _2, _3, evt:Position) -> float:
        u"Event duration as measured for that bead (un-normalized)"
        return evt.y

    @staticmethod
    @column_method(u"Event Completion")
    def _evtcompleted(_1, _2, _3, evt:Position) -> bool:
        u"Did the de-hybridisation occur prior to the cycle end ?"
        return evt.completed
