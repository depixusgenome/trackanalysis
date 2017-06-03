#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Finds peak positions on a bead"
from typing           import (Iterator, Tuple, Union, Sequence,
                              Optional, TYPE_CHECKING)
from copy             import deepcopy
from functools        import wraps
import numpy          as     np

from model            import PHASE
from data.trackitems  import Items, Cycles, Level, CYCLEKEY
from utils            import EVENTS_TYPE, EVENTS_DTYPE, asview
from .                import EventDetectionConfig

class EventsArray(np.ndarray):
    """Array with metadata."""
    # pylint: disable=unused-argument
    def __new__(cls, array, dtype=None, order=None, discarded = False):
        obj  = np.asarray(array, dtype = EVENTS_DTYPE, order=order).view(cls)
        obj.discarded = discarded
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        # pylint: disable=attribute-defined-outside-init
        self.discarded = getattr(obj, 'discarded', False)

class Events(Cycles, EventDetectionConfig, Items):
    u"""
    Class for iterating over events:

    * providing (column name, cycle id, event id) will extract an event on
      this column only.

    * providing (column name, ..., event id) will extract all events for a given bead.

    * ...

    """
    level = Level.event
    first = PHASE.measure
    last  = PHASE.measure
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        EventDetectionConfig.__init__(self, **kw)

    def __filterfcn(self):
        if self.filter is None:
            return lambda x, *_: x

        fcn = deepcopy(self.filter)
        @wraps(fcn)
        def _fcn(cycle, good, precision):
            fdt = np.copy(cycle)
            if good is None:
                fcn(fdt, precision = precision)
            else:
                fdt[good] = fcn(fdt[good], precision = precision)
            return fdt
        return _fcn

    def _iter(self, sel = None) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
        prec  = None if self.precision in (0., None) else self.precision
        track = self.track
        fcn   = self.__filterfcn()
        evts  = deepcopy(self.events)
        test  = None
        for key, cycle in super()._iter(sel):
            if test is None:
                test = cycle.dtype == EVENTS_DTYPE or cycle.dtype == 'O'
            if test:
                gen  = asview(cycle, EventsArray,
                              discarded = getattr(cycle, 'discarded', False))
            else:
                val  = self.getprecision(prec, track, key[0])
                good = np.isfinite(cycle)
                cnt  = good.sum()
                if cnt == 0:
                    gen = EventsArray([], discarded = True)
                else:
                    fdt = fcn(cycle, None if cnt == len(cycle) else good, val)
                    gen = EventsArray([(i, cycle[i:j])
                                       for i, j in evts(fdt, precision = val)])
            yield (key, gen)

    if TYPE_CHECKING:
        def keys(self, sel = None, beadsonly:Optional[bool] = None) -> Iterator[CYCLEKEY]:
            yield from super().keys(sel, beadsonly)

        def __getitem__(self, keys) -> Union['Events', Sequence[EVENTS_TYPE]]:
            return super().__getitem__(keys)

        def __iter__(self) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
            yield from super().__iter__()
