#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                      import (Dict, List, # pylint: disable=unused-import
                                           Tuple, Callable, cast)
from   functools                   import partial
import numpy                       as     np

from   model                       import PHASE
from   data.views                  import selectparent
from   control.processor.dataframe import DataFrameFactory
from   eventdetection.data         import Events, EventDetectionConfig
from   ..probabilities             import Probability
from   .selector                   import PeaksDict

@DataFrameFactory.adddoc
class PeaksDataFrameFactory(DataFrameFactory[PeaksDict]):
    """
    Transform a `PeaksDict` to one or more `pandas.DataFrame`.

    # Default Columns

    * *peakposition*
    * *averageduration*
    * *hybridisationrate*
    * *eventcount*

    # Aggregated Values

    If a *numpy* function or function name is provided in the measures, then it
    is applied to the concatenation of all event data.

    If a tuple of *numpy* functions or function names is provided in the
    measures, then the second function is applied to each event independently and
    the first is applied the array of results. Thus it is possible to measure the
    resolution of a peak:

    ```python
    >>> DataFrameTask(measures = dict(std = ('nanstd', 'nanmean')))
    ```

    # Getting one row per event

    One can also add information on events using:

    ```python
    >>> DataFrameTask(measures = dict(events = True))
    ```

    In such a case, added columns are:

    * *cycle*: event cycle
    * *start*: event start position
    * *length*: event length
    * *avg*: event average

    The following will also measure each event's std:

    ```python
    >>> DataFrameTask(measures = dict(events = dict(eventstd = np.nanstd)))
    ```

    or

    ```python
    >>> DataFrameTask(measures = dict(events = dict(eventstd = 'std')))
    ```
    """
    def __init__(self, task, frame, **kwa):
        super().__init__(task, frame)

        tmp   = selectparent(frame, Events)
        mdur  = (EventDetectionConfig() if tmp is None else tmp).events.select.minduration
        frate = frame.track.framerate

        self.__prob   = Probability(minduration = mdur, framerate = frate)
        self.__ends   = frame.track.phase.duration(..., PHASE.measure)

        meas          = dict(task.measures)
        meas.update(kwa)
        self.__events = meas.pop('events', None)
        if self.__events is True:
            self.__events = dict()

        if self.__events is not None:
            self.__events        = {i: self.getfunction(j) for i, j in self.__events.items()}
            self.__events['avg'] = np.nanmean

        add    = lambda verif: [(i, meas.pop(i)) for i in tuple(meas) if verif(meas[i])]
        isprop = lambda i: (isinstance(i, str)
                            and isinstance(getattr(Probability, i, None), property))
        ismeth = lambda i: (isinstance(i, str)
                            and callable(getattr(Probability, i, None)))
        isnp   = lambda i: ((isinstance(i, str) and hasattr(np, i))
                            or callable(i) and getattr(np, i.__name__, None) is i)
        method = lambda i: partial(lambda j, k: j(k[1]), getattr(Probability, i))

        self.__attrs  = ([('hybridisationrate', 'hybridisationrate'),
                          ('averageduration',   'averageduration'),
                          ('eventcount',        'nevents')]
                         +add(isprop))
        self.__np     = [(i, self.getfunction(j)) for i, j in add(isnp)]
        self.__aggs   = [(i, tuple(self.getfunction(k) for k in j))
                         for i, j in add(lambda x: isinstance(x, tuple))]
        self.__calls  = ([('peakposition', lambda i: i[0])]
                         + add(callable)
                         + [(cast(str, i), cast(Callable, method(j)))
                            for i, j in add(ismeth)]) # type: List[Tuple[str, Callable]]
        if any(j is not None for j in meas.values()):
            raise ValueError(f'Unrecognized measures {meas}')

    # pylint: disable=arguments-differ
    def _run(self, _1, _2, apeaks) -> Dict[str, np.ndarray]:
        peaks  = cast(Tuple[Tuple[float, np.ndarray], ...], tuple(apeaks))
        meas   = {} # type: Dict[str,np.ndarray]
        if self.__events:
            self.__eventmeasure(meas, peaks)
            counts = np.array([sum(len(j) > 0 for j in i) for _, i in peaks])
        else:
            counts = np.ones(len(peaks), dtype = 'i4')

        if self.__calls:
            self.__callmeasure(meas, peaks, counts)
        if self.__aggs:
            self.__aggmeasure(meas, peaks, counts)
        if self.__np:
            self.__npmeasure(meas, peaks, counts)
        if self.__attrs:
            self.__probmeasure(meas, peaks, counts)
        return meas

    def __callmeasure(self, meas, peaks, counts):
        meas.update({i: self.__peakmeasure(peaks, counts, j)  for i, j in self.__calls})

    def __probmeasure(self, meas, peaks, counts):
        prob  = self.__prob
        probs = [prob(i, self.__ends) for _, i in peaks]
        get   = lambda attr, obj: getattr(obj, attr)
        meas.update({i: self.__peakmeasure(probs, counts, partial(get, j))
                     for i, j in self.__attrs})

    def __npmeasure(self, meas, peaks, counts):
        curr = [[] for _ in self.__np] # type: List[List[np.ndarray]]
        for cnt, (_, pks) in zip(counts, peaks):
            tmp = [np.concatenate(i['data']) for i in pks if len(i)]
            arr = np.concatenate(tmp) if len(tmp) else np.empty(0, dtype = 'f4')
            for i, (_, j) in zip(curr, self.__np):
                i.append(np.full(cnt, j(arr)))

        if len(next(iter(curr), ())):
            meas.update({i: np.concatenate(j) for (i, _), j in zip(self.__np, curr)})

    def __aggmeasure(self, meas, peaks, counts):
        curr = [[] for _ in self.__aggs] # type: List[List[np.ndarray]]
        for cnt, (_, pks) in zip(counts, peaks):
            arrs = [np.concatenate(i['data']) for i in pks if len(i)]

            for i, (_, (agg, point)) in zip(curr, self.__aggs):
                i.append(np.full(cnt, agg([point(i) for i in arrs])))

        if len(next(iter(curr), ())):
            meas.update({i: np.concatenate(j) for (i, _), j in zip(self.__aggs, curr)})

    def __eventmeasure(self, meas, peaks):
        tmp   = {i: [] for i in self.__events.keys()} # type: Dict[str, List[np.ndarray]]
        tmp.update(cycle = [], start = [], length = [])

        append = lambda x, y: tmp[x].append(np.array(list(y)))
        for _, pks in peaks:
            append('cycle',  (i for i, j in enumerate(pks) if len(j)))
            append('length', (j['start'][-1]+len(j['data'][-1]) - j['start'][0]
                              for j in pks if len(j)))
            append('start',  (j['start'][0]  for j in pks if len(j)))

            arrs = tuple(np.concatenate(j['data']) for j in pks if len(j))
            for name, fcn in self.__events.items():
                append(name, (fcn(i) for i in arrs))

        if len(next(iter(tmp.values()), ())):
            meas.update({i: np.concatenate(j) for i, j in tmp.items()})

    @staticmethod
    def __peakmeasure(peaks, cnt, fcn):
        tmp = [np.full(cnt[i], fcn(j)) for i, j in enumerate(peaks)]
        return np.concatenate(tmp) if tmp else np.empty(0, dtype = 'f4')
