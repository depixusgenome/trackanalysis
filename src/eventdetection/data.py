#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Finds peak positions on a bead"
from typing           import Iterator, Tuple, Union, Sequence, TYPE_CHECKING
from copy             import deepcopy
from functools        import wraps
import numpy          as     np

from data.trackitems  import Items, Cycles, Level, CYCLEKEY
from utils            import escapenans, EVENTS_TYPE, EVENTS_DTYPE
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

    def __filterfcn(self):
        if self.filter is None:
            return lambda x, _: x

        fcn = deepcopy(self.filter)

        @wraps(fcn)
        def _fcn(cycle, precision):
            cycle = np.copy(cycle)
            with escapenans(cycle) as arr:
                fcn(arr, precision = precision)
            return cycle
        return _fcn

    def _iter(self, sel = None) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
        prec  = None if self.precision in (0., None) else self.precision
        track = self.track
        fcn   = self.__filterfcn()
        evts  = deepcopy(self.events)

        for key, cycle in super()._iter(sel):
            if cycle.dtype == 'O':
                gen = cycle
            else:
                val = evts.rawprecision(track, key[0]) if prec is None else prec
                fdt = fcn(cycle, val)
                gen = np.array([(i, cycle[i:j]) for i, j in evts(fdt, precision = val)],
                               dtype = EVENTS_DTYPE)
            yield (key, gen)

    if TYPE_CHECKING:
        def keys(self, sel = None) -> Iterator[CYCLEKEY]:
            yield from super().keys(sel)

        def __getitem__(self, keys) -> Union['Events', Sequence[EVENTS_TYPE]]:
            return super().__getitem__(keys)

        def __iter__(self) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
            yield from super().__iter__()
