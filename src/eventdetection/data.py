#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Finds peak positions on a bead"
from copy             import deepcopy
from functools        import wraps
import numpy          as     np

from data.trackitems  import Items, Cycles, Level
from utils            import escapenans
from signalfilter     import nanhfsigma
from .                import EventDetectionConfig

class Events(Cycles, EventDetectionConfig, Items):
    u"""
    Class for iterating over events:

    * providing (column name, cycle id, event id) will extract an event on
      this column only.

    * providing (column name, ..., event id) will extract all events for a given bead.

    * ...

    """
    level = Level.event
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        EventDetectionConfig.__init__(self, **kw)

    @staticmethod
    def __escapenans(fcn):
        @wraps(fcn)
        def _fcn(cycle):
            cycle = np.copy(cycle)
            with escapenans(cycle) as arr:
                fcn(arr)
            return cycle
        return _fcn

    def _iter(self, sel = None):
        itr  = super()._iter(sel)
        prec = self.precision
        if prec in (0, None):
            data = dict(itr)
            itr  = iter(data.items())
            prec = np.median(tuple(nanhfsigma(bead) for bead in data.values()))

        if self.filter is not None:
            filt           = deepcopy(self.filter)
            filt.precision = prec
            fcn            = self.__escapenans(filt)
        else:
            fcn            = lambda x:x

        evts           = deepcopy(self.events)
        evts.precision = prec

        dtype          = np.dtype([('start', 'i4'), ('data', 'O')])
        for key, cycle in itr:
            fdt = fcn(cycle)
            gen = np.array([(i, cycle[i:j]) for i, j in evts(fdt)], dtype = dtype)
            yield (key, gen)
