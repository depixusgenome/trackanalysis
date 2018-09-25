#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Selects peaks and yields all events related to each peak"
from   typing               import Callable, Optional, cast
import numpy                as     np

from utils                  import (initdefaults, asobjarray, asdataarrays, asview,
                                    updatecopy, EVENTS_DTYPE, EventsArray)
from signalfilter           import PrecisionAlg, PRECISION
from .alignment             import (PeakCorrelationAlignment, GELSPeakAlignment,
                                    PeakPostAlignment)
from .histogram             import Histogram
from .groupby               import (ByHistogram,PeakFinder)
from .peaksarray            import (Input, Output, # pylint: disable=unused-import
                                    PeaksArray, PeakListArray)

class PeakSelectorDetails: # pylint: disable=too-many-instance-attributes
    "Information useful to GUI"
    __slots__ = ('positions', 'histogram', 'minvalue', 'binwidth', 'corrections',
                 'peaks', 'events', 'ids')
    def __init__(self,     # pylint: disable=too-many-arguments
                 positions:   np.ndarray,
                 histogram:   np.ndarray,
                 minvalue:    float,
                 binwidth:    float,
                 corrections: np.ndarray,
                 peaks:       np.ndarray,
                 events:      EventsArray,
                 ids:         np.ndarray) -> None:
        self.positions   = positions
        self.histogram   = histogram
        self.minvalue    = minvalue
        self.binwidth    = binwidth
        self.corrections = corrections
        self.peaks       = peaks
        self.events      = events
        self.ids         = ids

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
    align:      Optional[PeakCorrelationAlignment] = None
    peakalign:  Optional[PeakPostAlignment]        = GELSPeakAlignment()
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

    def __measure(self, peak, evts):
        if self.histogram.zmeasure is None:
            return peak
        if isinstance(self.histogram.zmeasure, str):
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
        if self.peakalign:
            pkdlt = self.peakalign(self.peakalign.tostats(self.details2output(out)))
            pos  += pkdlt
            if delta is not None:
                delta += pkdlt
            out   = _findpeaks()
        return out

    def details2output(self, dtl:PeakSelectorDetails) -> PeakListArray:
        "yields results from precomputed details"
        vals = []
        for label, peak in enumerate(dtl.peaks):
            good = tuple(orig[pks == label]
                         for orig, pks in zip(dtl.events, dtl.ids)) # type: ignore
            if any(len(i) for i in good):
                evts = self.__move(good, dtl.corrections, dtl.events.discarded)
                vals.append((self.__measure(peak, evts), evts))
        return PeakListArray(vals, discarded = dtl.events.discarded)

    def __call__(self, evts: Input, precision: PRECISION = None) -> PeakListArray:
        return self.details2output(self.detailed(evts, precision))
