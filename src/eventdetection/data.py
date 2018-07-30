#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Finds peak positions on a bead"
from copy             import deepcopy
from functools        import wraps
from itertools        import chain
from typing           import Iterator, Tuple, Union, Sequence, cast, TYPE_CHECKING

import numpy          as     np

from model            import PHASE, Level
from data.views       import ITrackView, Cycles, CYCLEKEY, Beads
from utils            import EVENTS_TYPE, EVENTS_DTYPE, asview, EventsArray
from .                import EventDetectionConfig

class Events(Cycles, EventDetectionConfig, ITrackView):# pylint:disable=too-many-ancestors
    """
    This object provides a view on all events per cycle.

    Events are represented by an `EventArray`. The latter is a named numpy array.
    The "start" field is the index in phase 5 when the event begins. The "data"
    field is the event data. There is also a `discarded` attribute which indicates
    the number of cycles which are filled with missing values:

    ```python
    >>> for (ibead, icycle), data in events:
    ...     assert isinstance(ibead, int)
    ...     assert isinstance(icycle, int)
    ...     assert all(isinstance(i, int)        for i in data['start'].dtype)
    ...     assert all(isinstance(i, np.ndarray) for i in data['data'].dtype)
    ```

    It can be configured as a `Cycles` object:
    """
    if __doc__:
        __doc__ += '\n'.join(Cycles.__doc__.split('\n'))
    level = Level.event
    first = PHASE.measure
    last  = PHASE.measure
    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        EventDetectionConfig.__init__(self, **kw)

    def _iter(self, sel = None) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
        if isinstance(self.data, Events):
            yield from ((i, cast(Sequence[EVENTS_TYPE], self.data[i]))
                        for i in self.keys(self.selected if sel is None else sel))
            return

        tmp = super()._iter(sel)
        for key, cycle in tmp:
            test = cycle.dtype == EVENTS_DTYPE or cycle.dtype == 'O'
            itrs = (key, cycle)
            yield from (self.__testiter(itrs, tmp)     if test        else
                        self.__filterediter(itrs, tmp) if self.filter else
                        self.__simpleiter(itrs, tmp))
            break

    def bead(self, ibead):
        "return the data for a full bead"
        if (isinstance(self.data, Beads)
                and not self.data.cycles
                and hasattr(self.events, "computeall")):
            prec   = None if self.precision in (0., None) else self.precision
            data   = self.data[ibead]
            meas   = self.track.phase.select(..., PHASE.measure)
            ints   = self.events.computeall(data,
                                            self.getprecision(prec, self.track, ibead),
                                            meas,
                                            self.track.phase.select(..., PHASE.measure+1)
                                           )
            return (EventsArray([(j, data[i+j:i+k]) for j, k in cyc],
                                discarded = len(cyc) == 0)
                    for i, cyc in zip(meas, ints))
        return iter(self[ibead, ...].values())

    def __simpleiter(self, first, itrs) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
        prec      = None if self.precision in (0., None) else self.precision
        track     = self.track
        evts      = deepcopy(self.events).compute

        val, curb = self.getprecision(prec, track, first[0][0]), first[0][0]
        ints      = evts(first[1], precision = val)
        gen       = EventsArray([(i, first[1][i:j]) for i, j in ints],
                                discarded = len(ints) == 0)
        yield (first[0], gen)

        for key, cycle in itrs:
            if curb != key[0]:
                val, curb = self.getprecision(prec, track, key[0]), key[0]
            ints = evts(cycle, precision = val)
            gen  = EventsArray([(i, cycle[i:j]) for i, j in ints],
                               discarded = len(ints) == 0)
            yield (key, gen)

    @staticmethod
    def __fitered_out(fcn, evts, key, cycle, val):
        good = np.isfinite(cycle)
        cnt  = good.sum()
        if cnt == 0:
            return key, EventsArray([], discarded = True)

        fdt = fcn(cycle, None if cnt == len(cycle) else good, val)
        gen = EventsArray([(i, cycle[i:j]) for i, j in evts(fdt, precision = val)])
        return key, gen

    def __filterfcn(self):
        if self.filter is None:
            return None

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

    def __filterediter(self, first, itrs) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
        prec  = None if self.precision in (0., None) else self.precision
        fcn   = self.__filterfcn()
        evts  = deepcopy(self.events).compute
        fout  = self.__fitered_out

        key, cycle  = first
        val, curb   = self.getprecision(prec, self.track, key[0]), key[0]
        yield fout(fcn, evts, key, cycle, val)

        for key, cycle in chain((first,), itrs):
            if curb != key[0]:
                val, curb = self.getprecision(prec, self.track, key[0]), key[0]
            yield fout(fcn, evts, key, cycle, val)

    @staticmethod
    def __testiter(first, itrs) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
        for key, cycle in chain((first,), itrs):
            gen  = asview(cycle, EventsArray,
                          discarded = getattr(cycle, 'discarded', False))
            yield (key, gen)

    if TYPE_CHECKING:
        # pylint: disable=useless-super-delegation
        def keys(self, sel = None) -> Iterator[CYCLEKEY]:
            yield from super().keys(sel)

        def __getitem__(self, keys) -> Union['Events', Sequence[EVENTS_TYPE]]:
            return cast(Union['Events', Sequence[EVENTS_TYPE]], super().__getitem__(keys))

        def __iter__(self) -> Iterator[Tuple[CYCLEKEY, Sequence[EVENTS_TYPE]]]:
            yield from super().__iter__()
