#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Simpler PeaksDict detection: merging and selecting the sections in the signal detected as flat"
from   typing                       import (Union, Iterator, Iterable, Tuple,
                                            Type, List, cast)
from   copy                         import copy as shallowcopy
from   functools                    import partial

import pandas                       as     pd
import numpy                        as     np

from utils.decoration               import addto, addproperty, extend
from control.processor.dataframe    import DataFrameProcessor
from eventdetection                 import EventDetectionConfig
from eventdetection.data            import Events
from model                          import PHASE
from model.__scripting__            import Tasks
from data.track                     import Track, Axis
from data.views                     import Cycles
from data.tracksdict                import TracksDict
from data.__scripting__.dataframe   import adddataframe
from data.__scripting__.tracksdict  import TracksDictOperator
from ..selector                     import PeakSelectorDetails
from ..probabilities                import Probability
from ..processor.selector           import PeaksDict, PeakListArray
from ..processor                    import (PeakSelectorTask, PeakCorrelationAlignmentTask,
                                            PeakProbabilityTask)

@addto(Track) # type: ignore
@property
def peaks(self) -> PeaksDict:
    "returns peaks found"
    return self.apply(*Tasks.defaulttasklist(self, Tasks.peakselector))

@extend(PeaksDict)
class _PeaksDictMixin:
    def swap(self,
             data: Union[Track, TracksDict, Cycles, str, Axis] = None,
             axis: Union[str, Axis] = None) -> PeaksDict:
        "Returns indexes or values in data at the same key and index"
        this = cast(PeaksDict, self)

        if isinstance(data, TracksDict):
            if axis is not None:
                axis = Axis(axis)

            if this.track.key in data:
                data = cast(Track, data[this.track.key])
            elif axis is not None:
                data = cast(Track, data[Axis(axis).name[0]+this.track.key])
            else:
                raise KeyError("Unknown data")

        if isinstance(data, (str, Axis)):
            data = Track(path = this.track.path, axis = data)

        if isinstance(data, Track):
            data = data.cycles # type: ignore

        return this.withaction(partial(self._swap, cast(Cycles, data).withphases(PHASE.measure)))

    def concatenated(self, alltogether = True) -> PeaksDict:
        """
        Add a method that returns a cycle vector, with NaN values where no
        events is defined.
        """
        fcn = self._concatenate_all if alltogether else self._concatenate_iter
        return cast(PeaksDict, self).withaction(fcn)

    def index(self) -> PeaksDict:
        "Returns indexes at the same key and positions"
        return cast(PeaksDict, self).withaction(self._index)

    def withmeasure(self, singles = np.nanmean, multiples = None) -> 'PeaksDict':
        "Returns a measure per events."
        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))
        return cast(PeaksDict, self).withaction(partial(self._measure, singles, multiples))

    @classmethod
    def _measure(cls, singles, multiples, _, info):
        fcn = cls._array2measure
        return info[0], ((i, fcn(singles, multiples, j)) for i, j in info[1])

    @classmethod
    def _array2measure(cls, singles, multiples, arr):
        if arr.dtype == 'O':
            arr[:] = [None                    if i == 0      else
                      singles  (i['data'][0]) if len(i) == 1 else
                      multiples(i['data'])
                      for i in arr[:]]
        else:
            arr['data'] = [singles(i) for i in arr['data']]
        return arr

    @classmethod
    def _index(cls, _, info):
        return info[0], ((i, cls._array2slice(j)) for i, j in info[1])

    @staticmethod
    def _array2slice(evts):
        for i, evt in enumerate(evts):
            evts[i] = np.array([slice(k, k+len(l)) for k, l in evt], dtype = 'O')
        return evts

    @classmethod
    def _swap(cls, data, _, info):
        return info[0], ((i, cls._swap_evts(info[0], data, j)) for i, j in info[1])

    @staticmethod
    def _swap_evts(bead, cycles, evts):
        for i, evt in enumerate(evts):
            evts[i][:] = [(k, cycles[bead,i][k:k+len(l)]) for k, l in evt]
        return evts

    @staticmethod
    def _concatenate_peak(lens, arr, evts):
        if arr is None:
            arr = np.full(lens[-1], np.NaN, dtype = 'f4')

        for i, cycle in zip(lens, evts):
            for start, data in cycle:
                arr[i+start:i+start+len(data)] = data
        return arr

    @classmethod
    def _concatenate_all(cls, frame, info):
        lens = np.insert((frame.track.phase.duration(..., PHASE.measure)+1).cumsum(),
                         0, 0)
        out  = None
        for _, i in info[1]:
            out = cls._concatenate_peak(lens, out, i)
        return info[0], out

    @classmethod
    def _concatenate_iter(cls, frame, info):
        lens = np.insert((frame.track.phase.duration(..., PHASE.measure)+1).cumsum(),
                         0, 0)
        out  = ((i, cls._concatenate_peak(lens, None, j)) for i, j in info[1])
        return info[0], out

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
    zero        = property(lambda self: self.output[0][0] if len(self.output) else 0)
    events      = property(lambda self: self.details.events)
    ids         = property(lambda self: self.details.ids)

    def setparams(self, params):
        "sets params and applies it to positions"
        self.params = params
        self.details.transform(params)

    @property
    def output(self) -> PeakListArray:
        "yields results from precomputed details"
        if self.frame is None:
            return PeakListArray([], discarded = 0)
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

        ends        = trk.phase.duration(..., PHASE.measure)
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

class PeaksTracksDictOperator(TracksDictOperator, peaks = TracksDict):
    "Add dataframe method to tracksdict"
    def dataframe(self, *tasks, transform = None, assign = None, **kwa):
        """
        Concatenates all dataframes obtained through *track.peaks.dataframe*

        See documentation in *track.peaks.dataframe* for other options
        """
        return self._dictview().dataframe(Tasks.peakselector, *tasks,
                                          transform = transform,
                                          assign    = assign,
                                          **kwa)

adddataframe(PeaksDict)

__all__: List[str] = ['PeakSelectorTask', 'PeakCorrelationAlignmentTask', 'PeakProbabilityTask']
