#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selects peaks and yields all events related to each peak"
from   typing               import Callable, Optional, cast
import numpy                as     np

from utils                  import (initdefaults, asobjarray, asdataarrays, asview,
                                    updatecopy, EVENTS_DTYPE, EventsArray,
                                    dataclass)
from signalfilter           import PrecisionAlg, PRECISION
from .alignment             import PeakCorrelationAlignment, PeakPostAlignment
from .histogram             import Histogram
from .groupby               import ByHistogram,PeakFinder
from .peaksarray            import Input, PeaksArray, PeakListArray

@dataclass
class PeakSelectorDetails: # pylint: disable=too-many-instance-attributes
    "Information useful to GUI"
    __slots__ = ('positions', 'histogram', 'minvalue', 'binwidth', 'corrections',
                 'peaks', 'events', 'ids')
    positions:   np.ndarray
    histogram:   np.ndarray
    minvalue:    float
    binwidth:    float
    corrections: np.ndarray
    peaks:       np.ndarray
    events:      EventsArray
    ids:         np.ndarray

    def __iter__(self):
        return iter(getattr(self, i) for i in self.__slots__)

    def __getitem__(self, val):
        return getattr(self, self.__slots__[val])

    def transform(self, params):
        "sets params and applies it to positions"
        self.peaks[:]     = (self.peaks-params[1])*params[0]
        self.positions[:] = [(i-params[1])*params[0] for i in self.positions]
        for evt in self.events:
            evt['data'][:] = [(i-params[1])*params[0] for i in evt['data']]

        self.minvalue  = (self.minvalue-params[1])*params[0]
        self.binwidth *= params[0]

    def output(self, zmeasure) -> PeakListArray:
        "yields results from precomputed details"
        zmeas: Callable = (zmeasure if callable(zmeasure) else
                           None     if zmeasure is None   else
                           getattr(np, cast(str, zmeasure)))
        vals = []
        for label, peak in enumerate(self.peaks):
            good = tuple(orig[pks == label]
                         for orig, pks in zip(self.events, self.ids)) # type: ignore
            if any(len(i) for i in good):
                evts = self.__move(good, self.corrections, self.events.discarded)
                vals.append((self.__measure(zmeas, peak, evts), evts))
        return PeakListArray(vals, discarded = self.events.discarded)

    @staticmethod
    def __move(evts, deltas, discarded) -> PeaksArray:
        first = next((i for i in evts if i is not None), None)
        if first is None:
            return PeaksArray([], dtype = 'O', discarded = discarded)

        if deltas is None:
            objs = tuple(evts)

        else:
            if isinstance(first, tuple) or first.dtype == EVENTS_DTYPE:
                def _add(evt, delta):
                    if len(evt) > 0:
                        evt['data'] += delta
                    return evt
            else:
                def _add(evt, delta):
                    return evt if len(evt) == 0 else evt + delta
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

    @staticmethod
    def __measure(zmeas, peak, evts):
        if zmeas is None:
            return peak

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

        vals = [_measure(i) for i in evts if i is not None and len(i) > 0]
        return zmeas(np.concatenate(vals))

class PeakSelector(PrecisionAlg):
    """
    Find binding positions and selects relevant events.

    # Attributes

    * `histogram`: algorithm for projecting all events onto the z axis. Multiple
    events in a single neighborhood create peaks. These are the binding positions.
    * `align`: algorithm for aligning cycles so as to minimize peak widths in the histogram.
    * `finder`: algorithm for extracting binding positions from the histogram of
    *aligned* events.
    """

    rawfactor                                      = 2.
    histogram                                      = Histogram(edge = 2)
    align:      Optional[PeakCorrelationAlignment] = PeakCorrelationAlignment()
    peakalign:  Optional[PeakPostAlignment]        = None
    finder:     PeakFinder                         = ByHistogram()

    if __doc__:
        __doc__ += "\n    # Default algorithms\n"
        __doc__ += f"\n    ## `{type(align).__module__}.{type(align).__qualname__}`\n"
        __doc__ += (cast(str, type(PeakCorrelationAlignment).__doc__)
                    .replace("\n    #", "\n    ##"))
        __doc__ += f"\n    ## `{type(finder).__module__}.{type(finder).__qualname__}`\n"
        __doc__ += cast(str, type(finder).__doc__).replace("\n    #", "\n    ##")

    @initdefaults(frozenset(locals()) - {'rawfactor'})
    def __init__(self, **_):
        super().__init__(**_)

    def detailed(self, evts: Input, precision: PRECISION = None) -> PeakSelectorDetails:
        "returns computation details"
        orig   = asobjarray(evts)
        orig   = asview(orig, PeaksArray,
                        discarded = sum(getattr(i, 'discarded', 0) for i in orig))
        events = asdataarrays(tuple(orig)) # create a copy before passing to function

        precision = self.getprecision(precision, events)

        projector = updatecopy(self.histogram, True, precision = precision)

        pos       = projector.eventpositions(events)
        if callable(self.align):
            delta  = self.align(pos, projector = projector) # pylint: disable=not-callable
            pos   += delta
        else:
            delta  = None

        def _findpeaks():
            histdata   = projector.projection(pos, zmeasure = None)
            peaks, ids = self.finder(events    = events,
                                     hist      = histdata,
                                     pos       = pos,
                                     precision = precision)
            return PeakSelectorDetails(pos, histdata[0], histdata[1], histdata[2],
                                       delta, peaks, orig, ids)
        out = _findpeaks()
        if callable(self.peakalign):
            # pylint: disable=not-callable
            pkdlt = self.peakalign(self.peakalign.tostats(self.details2output(out)))
            pos  += pkdlt
            if delta is not None:
                delta += pkdlt
            out   = _findpeaks()
        return out

    def details2output(self, dtl:PeakSelectorDetails) -> PeakListArray:
        "return results from precomputed details"
        return dtl.output(self.histogram.zmeasure)

    def __call__(self, evts: Input, precision: PRECISION = None) -> PeakListArray:
        return self.details2output(self.detailed(evts, precision))
