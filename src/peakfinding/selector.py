#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Selects peaks and yields all events related to each peak"
from   typing       import Iterable, Iterator, Tuple, Optional, Union, Sequence
from   copy         import copy
from   collections  import namedtuple
import numpy    as      np

from utils      import (initdefaults, asobjarray, asdataarrays,
                        EVENTS_TYPE, EVENTS_DTYPE)
from .alignment import PeakCorrelationAlignment
from .histogram import (Histogram, PeakFinder, # pylint: disable=unused-import
                        ZeroCrossingPeakFinder, GroupByPeak)

EventsOutput        = Sequence[Union[None, EVENTS_TYPE, Sequence[EVENTS_TYPE]]]
Input               = Union[Iterable[Iterable[np.ndarray]], Sequence[EVENTS_TYPE]]
Output              = Tuple[float, EventsOutput]
PeakSelectorDetails = namedtuple('PeakSelectorDetails',
                                 ['positions', 'histogram', 'minvalue', 'binwidth',
                                  'corrections', 'peaks', 'events', 'ids'])

class PeakSelector:
    u"Selects peaks and yields all events related to each peak"
    histogram = Histogram(edge = 2)
    align     = PeakCorrelationAlignment()
    find      = ZeroCrossingPeakFinder() # type: PeakFinder
    group     = GroupByPeak()
    @initdefaults
    def __init__(self, **_):
        pass

    @staticmethod
    def __move(evts, deltas):
        first = next((i for i in evts if i is not None), None)
        if first is None:
            return evts

        if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
            def _add(evt, delta):
                if len(evt) == 0:
                    return None
                elif len(evt) == 1:
                    return evt[0][0], evt[0][1]+delta
                else:
                    evt['data'] += delta
                    return evt
        else:
            def _add(evt, delta):
                if len(evt) == 0:
                    return None
                elif len(evt) == 1:
                    return evt[0]+delta
                else:
                    return evt + delta

        objs = tuple(_add(*item) for item in zip(evts, deltas))
        if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
            if all(isinstance(i, tuple) for i in objs):
                ret = np.empty((len(objs),), dtype = EVENTS_DTYPE)
                ret['data']  = tuple(i for _, i in objs)
                ret['start'] = tuple(i for i, _ in objs)
                return ret
        elif all(np.isscalar(i) for i in objs):
            return np.array(objs, dtype = 'f4')
        return asobjarray(objs)

    def __measure(self, peak, evts):
        zmeas = self.histogram.zmeasure
        if zmeas is None:
            return peak

        first = next((i for i in evts if i is not None), None)
        if first is None:
            return peak

        if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
            def _measure(item):
                if isinstance(item, tuple):
                    return [zmeas(item[1])]
                else:
                    return [zmeas(i) for i in item['data']]
        else:
            def _measure(item):
                if np.isscalar(item[0]):
                    return [zmeas(item)]
                else:
                    return [zmeas(i[1]) for i in item]

        vals = [_measure(i) for i in evts if i is not None]
        return zmeas(np.concatenate(vals))

    def detailed(self, evts: Input, precision: Optional[float] = None) -> PeakSelectorDetails:
        "returns computation details"
        original  = asobjarray(evts)
        events    = asdataarrays(tuple(original))
        projector = copy(self.histogram)
        projector.precision = projector.getprecision(precision, events)

        pos = projector.eventpositions(events)
        if self.align is not None:
            delta  = self.align(pos, projector = projector)
            pos   += delta
        else:
            delta  = 0.

        hist, minv, binwidth = projector.projection(pos, zmeasure = None)
        peaks = self.find (hist, minv, binwidth)
        ids   = self.group(peaks, pos, precision = precision)
        return PeakSelectorDetails(pos, hist, minv, binwidth, delta, peaks, original, ids)

    def details2output(self, dtl:PeakSelectorDetails) -> Iterator[Output]:
        "yields results from precomputed details"
        for label, peak in enumerate(dtl.peaks):
            good = tuple(orig[pks == label] for orig, pks in zip(dtl.events, dtl.ids))
            if any(len(i) for i in good):
                evts = self.__move(good, dtl.corrections)
                yield (self.__measure(peak, evts), evts)

    def __call__(self, evts: Input, precision: Optional[float] = None) -> Iterator[Output]:
        yield from self.details2output(self.detailed(evts, precision))
