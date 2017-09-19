#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simpler PeaksDict detection: merging and selecting the sections in the signal detected as flat"
import sys
from   typing                       import (Union, Iterator, Iterable, Type,
                                            Callable, Tuple, List, cast)
from   copy                         import copy as shallowcopy

import pandas                       as     pd
import numpy                        as     np

from utils.decoration               import addto
from control.processor.dataframe    import DataFrameProcessor
from eventdetection                 import EventDetectionConfig
from eventdetection.data            import Events
from model                          import PHASE
from data                           import Track
from ..selector                     import PeakSelectorDetails
from ..probabilities                import Probability
from ..data                         import PeaksDict, PeakOutput

Tasks:           Type     = sys.modules['model.__scripting__'].Tasks
defaulttasklist: Callable = sys.modules['data.__scripting__'].defaulttasklist

@addto(Track) # type: ignore
@property
def peaks(self) -> PeaksDict:
    "returns peaks found"
    return self.apply(*defaulttasklist(self.path, Tasks.peakselector, self.cleaned))

class Detailed:
    "Deals with easy acccess to peaks data"
    def __init__(self, frame, det):
        self.frame       = frame
        self.details     = det

    positions   = property(lambda self: self.details.positions)
    histogram   = property(lambda self: self.details.histogram)
    minvalue    = property(lambda self: self.details.minvalue)
    binwidth    = property(lambda self: self.details.binwidth)
    corrections = property(lambda self: self.details.corrections)
    peaks       = property(lambda self: self.details.peaks)
    zero        = property(lambda self: next(self.output)[0])
    events      = property(lambda self: self.details.events)
    ids         = property(lambda self: self.details.id)

    @property
    def output(self) -> Iterator[PeakOutput]:
        "yields results from precomputed details"
        return self.frame.config.details2output(self.details)

    @property
    def probabilities(self) -> Iterator[Tuple[float, Probability]]:
        "yields results from precomputed details"
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
        if norm == 'events':
            val = 1./self.frame.config.histogram.kernelarray().max()
        elif norm in (1., 'probability'):
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

@addto(PeaksDict)
def dataframe(self, **kwa) -> pd.DataFrame:
    """
    converts to a pandas dataframe.

    Columns are:

        * *track*
        * *bead*
        * *peakposition*
        * *averageduration*
        * *hybridizationrate*
        * *eventcount*

    Additionnal columns can be added with kwargs. The key is the title. The value
    can either be:

        * a callable with all events for that peak as input and expecting a number
        as output,
        * a attribute name from peakfinding.probabilities.Probability

    """
    return DataFrameProcessor.apply(shallowcopy(self), measures = kwa, merge = True)

__all__: List[str] = []
