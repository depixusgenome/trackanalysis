#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Finds peak positions on a bead"
from typing           import (Iterator, Tuple, Union, Sequence,
                              Optional, cast, TYPE_CHECKING)
from copy             import deepcopy
from functools        import wraps, partial
import numpy          as     np

from model            import PHASE, Level
from data.track       import Track
from data.views       import ITrackView, Cycles, CYCLEKEY
from utils            import EVENTS_TYPE, EVENTS_DTYPE, asview, EventsArray
from .                import EventDetectionConfig

class Events(Cycles, EventDetectionConfig, ITrackView):# pylint:disable=too-many-ancestors
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
        if isinstance(self.data, Events):
            yield from ((i, cast(Sequence[EVENTS_TYPE], self.data[i]))
                        for i in self.keys(self.selected if sel is None else sel))
            return

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

    def swap(self, data: Union[Track, Cycles] = None) -> 'Events':
        "Returns indexes or values in data at the same key and index"
        data = getattr(data, 'cycles', data)
        return self.withaction(partial(self.__swap, data))

    def index(self) -> 'Events':
        "Returns indexes at the same key and positions"
        return self.withaction(self.__index)

    @staticmethod
    def __index(_, info):
        info[1]['data'] = [range(i,i+len(j)) for i, j in info[1]]
        return info

    @staticmethod
    def __swap(data, _, info):
        tmp             = data[info[0]]
        info[1]['data'] = [tmp[i:i+len(j)] for i, j in info[1]]
        return info

    if TYPE_CHECKING:
        # pylint: disable=useless-super-delegation
        def keys(self, sel = None, beadsonly:Optional[bool] = None) -> Iterator[CYCLEKEY]:
            yield from super().keys(sel, beadsonly)

        def __getitem__(self, keys) -> Union['Events', Sequence[EVENTS_TYPE]]:
            return cast(Union['Events', Sequence[EVENTS_TYPE]], super().__getitem__(keys))

        def __iter__(self) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
            yield from super().__iter__()
