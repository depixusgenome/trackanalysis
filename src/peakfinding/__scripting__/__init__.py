#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simpler PeaksDict detection: merging and selecting the sections in the signal detected as flat"
from   typing                       import (Union, Iterator, Iterable,
                                            Tuple, List, cast)
from   copy                         import copy as shallowcopy

import pandas                       as     pd
import numpy                        as     np

from utils.decoration               import addto
from control.processor.dataframe    import DataFrameProcessor
from eventdetection                 import EventDetectionConfig
from eventdetection.data            import Events
from model                          import PHASE
from model.__scripting__            import Tasks
from data                           import Track
from data.__scripting__.dataframe   import adddataframe
from ..selector                     import PeakSelectorDetails
from ..probabilities                import Probability
from ..processor.selector           import PeaksDict, PeakOutput

@addto(Track) # type: ignore
@property
def peaks(self) -> PeaksDict:
    "returns peaks found"
    return self.apply(*Tasks.defaulttasklist(self, Tasks.peakselector))

class Detailed:
    "Deals with easy acccess to peaks data"
    def __init__(self, frame, det):
        self.frame  = frame
        self.params = 1., 0.
        if det is None:
            self.details = PeakSelectorDetails(np.ones(0, dtype = 'f4'),
                                               np.ones(0, dtype = 'f4'),
                                               0., 1e-3,
                                               np.ones(0, dtype = 'f4'),
                                               np.ones(0, dtype = 'f4'),
                                               np.ones(0, dtype = 'f4'),
                                               np.ones(0, dtype = 'i4'))
        else:
            self.details = det

    positions   = property(lambda self: self.details.positions)
    histogram   = property(lambda self: self.details.histogram)
    minvalue    = property(lambda self: self.details.minvalue)
    binwidth    = property(lambda self: self.details.binwidth)
    corrections = property(lambda self: self.details.corrections)
    peaks       = property(lambda self: self.details.peaks)
    zero        = property(lambda self: next(self.output, [0])[0])
    events      = property(lambda self: self.details.events)
    ids         = property(lambda self: self.details.ids)

    def setparams(self, params):
        "sets params and applies it to positions"
        self.params       = params
        self.peaks[:]     = (self.peaks-params[1])*params[0]
        self.positions[:] = [(i-params[1])*params[0] for i in self.positions]
        for evt in self.events:
            evt['data'][:] = [(i-params[1])*params[0] for i in evt['data']]

        lst          = list(self.details)
        lst[2]       = (lst[2]-params[1])*params[0]
        lst[3]      *= params[0]
        self.details = type(self.details)(*lst)

    @property
    def output(self) -> Iterator[PeakOutput]:
        "yields results from precomputed details"
        if self.frame is None:
            return iter(tuple())
        return self.frame.config.details2output(self.details)

    @property
    def probabilities(self) -> Iterator[Tuple[float, Probability]]:
        "yields results from precomputed details"
        if self.frame is None:
            return iter(tuple())

        trk  = self.frame.track

        evts = self.frame.data
        while not isinstance(evts, EventDetectionConfig):
            evts = getattr(evts, 'data', None)
            if evts is None:
                raise ValueError('Could not find a minduration')
        minduration = evts.events.select.minduration

        ends        = trk.phaseduration(..., PHASE.measure)
        prob        = Probability(minduration = minduration,
                                  framerate   = trk.framerate)
        return iter((i[0], prob(i[1], ends)) for i in self.output)

    def xaxis(self, stretch = 1., bias = 0.):
        "returns the histogram's x-axis"
        xvals = np.arange(len(self.histogram))*self.binwidth+self.minvalue
        xvals = (xvals-bias)*stretch
        return xvals

    def yaxis(self, norm = 'events'):
        "returns the histogram's y-axis"
        if norm == 'events' and self.frame is not None:
            val = 1./self.frame.config.histogram.kernelarray().max()
        elif norm in (1., 'probability') and len(self.histogram):
            val = 1./self.histogram.sum()
        else:
            val = 1.
        return self.histogram*val

@addto(PeaksDict)
def detailed(self, ibead, precision: float = None) -> Union[Iterator[Detailed], Detailed]:
    "detailed output from config"
    if ibead is Ellipsis:
        return iter(self.detailed(i, precision) for i in self.keys())
    if isinstance(ibead, Iterable):
        return iter(self.detailed(i, precision) for i in set(self.keys) & set(ibead))

    prec = self._precision(ibead, precision) # pylint: disable=protected-access
    if isinstance(self.data, PeaksDict):
        if self.actions:
            raise NotImplementedError()
        return self.data.detailed(ibead, precision) # type: ignore
    evts = iter(i for _, i in self.data[ibead,...])
    return Detailed(self, self.config.detailed(evts, prec))

adddataframe(PeaksDict)
__all__: List[str] = []
