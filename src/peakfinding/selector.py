#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Selects peaks and yields all events related to each peak"
from   typing               import (Iterable, Iterator, Tuple, Union, Sequence,
                                    Callable, cast)
from   collections          import namedtuple
import numpy    as              np

from utils                  import (initdefaults, asobjarray, asdataarrays, asview,
                                    updatecopy, EVENTS_TYPE, EVENTS_DTYPE, EventsArray)
from signalfilter           import PrecisionAlg, PRECISION
from .alignment             import PeakCorrelationAlignment
from .histogram             import (Histogram, # pylint: disable=unused-import
                                    ZeroCrossingPeakFinder, PeakFinder,
                                    GroupByPeakAndBase, GroupByPeak)

EventsOutput        = Sequence[Union[None, EVENTS_TYPE, Sequence[EVENTS_TYPE]]]
Input               = Union[Iterable[Iterable[np.ndarray]], Sequence[EVENTS_TYPE]]
Output              = Tuple[float, EventsOutput]
PeakSelectorDetails = namedtuple('PeakSelectorDetails',
                                 ['positions', 'histogram', 'minvalue', 'binwidth',
                                  'corrections', 'peaks', 'events', 'ids'])

class PeaksArray(EventsArray):
    """Array with metadata."""
    _discarded = 0
    _dtype     = None

class PeakSelector(PrecisionAlg):
    u"Selects peaks and yields all events related to each peak"
    rawfactor = 2.
    histogram = Histogram(edge = 2)
    align     = PeakCorrelationAlignment()
    find      = ZeroCrossingPeakFinder() # type: PeakFinder
    group     = GroupByPeakAndBase()     # type: GroupByPeak
    @initdefaults(frozenset(locals()) - {'rawfactor'})
    def __init__(self, **_):
        super().__init__(**_)

    @staticmethod
    def __move(evts, deltas, discarded) -> PeaksArray:
        first = next((i for i in evts if i is not None), None)
        if first is None:
            return PeaksArray([], dtype = 'O', discarded = discarded)

        if deltas is None:
            objs = tuple(i if len(i) else None for i in evts)

        else:
            if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
                def _add(evt, delta):
                    if len(evt) == 0:
                        return None

                    if len(evt) == 1:
                        return evt[0][0], evt[0][1]+delta

                    evt['data'] += delta
                    return evt
            else:
                def _add(evt, delta):
                    return (None         if len(evt) == 0 else
                            evt[0]+delta if len(evt) == 1 else
                            evt + delta)

            objs = tuple(_add(*item) for item in zip(evts, deltas))

        if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
            if all(isinstance(i, tuple) for i in objs):
                ret = asview(np.empty((len(objs),), dtype = EVENTS_DTYPE),
                             view      = PeaksArray,
                             discarded = discarded)
                ret['data']  = tuple(i for _, i in objs)
                ret['start'] = tuple(i for i, _ in objs)
                return ret
        elif all(np.isscalar(i) for i in objs):
            return PeaksArray(objs, dtype = 'f4', discarded = discarded)

        return asobjarray(objs, PeaksArray, discarded = discarded)

    def __measure(self, peak, evts):
        if self.histogram.zmeasure is None:
            return peak
        elif isinstance(self.histogram.zmeasure, str):
            zmeas = getattr(np, self.histogram.zmeasure)
        else:
            zmeas = cast(Callable, self.histogram.zmeasure)

        if getattr(evts, 'dtype', 'f4') == EVENTS_DTYPE:
            return zmeas([zmeas(i) for i in evts['data']])

        first = next((i for i in evts if i is not None), None)
        if first is None:
            return peak

        if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
            def _measure(item):
                return ([zmeas(item[1])]        if isinstance(item, tuple)  else
                        [zmeas(i) for i in item['data']])
        else:
            def _measure(item):
                return ([zmeas(item)]           if np.isscalar(item[0])     else
                        [zmeas(i[1]) for i in item])

        vals = [_measure(i) for i in evts if i is not None]
        return zmeas(np.concatenate(vals))

    def detailed(self, evts: Input, precision: PRECISION = None) -> PeakSelectorDetails:
        "returns computation details"
        orig   = asobjarray(evts)
        orig   = asview(orig, PeaksArray,
                        discarded = sum(getattr(i, 'discarded', 0) for i in orig))
        events = asdataarrays(tuple(orig)) # create a copy before passing to function

        precision = self.getprecision(precision, events)

        projector = updatecopy(self.histogram, True, precision = precision)

        pos       = projector.eventpositions(events)
        if self.align is not None:
            delta  = self.align(pos, projector = projector)
            pos   += delta
        else:
            delta  = None

        hist, minv, binwidth = projector.projection(pos, zmeasure = None)
        peaks = self.find (hist, minv, binwidth)
        ids   = self.group(peaks, pos, precision = precision)
        return PeakSelectorDetails(pos, hist, minv, binwidth, delta, peaks, orig, ids)

    def details2output(self, dtl:PeakSelectorDetails) -> Iterator[Output]:
        "yields results from precomputed details"
        for label, peak in enumerate(dtl.peaks):
            good = tuple(orig[pks == label] for orig, pks in zip(dtl.events, dtl.ids))
            if any(len(i) for i in good):
                evts = self.__move(good, dtl.corrections, dtl.events.discarded)
                yield (self.__measure(peak, evts), evts)

    def __call__(self, evts: Input, precision: PRECISION = None) -> Iterator[Output]:
        yield from self.details2output(self.detailed(evts, precision))
