#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing     import Dict, List, Tuple, Callable, Iterable, cast
from   functools  import partial
import pandas     as     pd
import numpy      as     np

from   taskcontrol.processor.dataframe import DataFrameFactory
from   .probabilities                  import Probability, peakprobability
from   .peakfiltering                  import PeakStatusComputer
from   .selector                       import PeaksDict

@DataFrameFactory.adddoc
class PeaksDataFrameFactory(  # pylint: disable=too-many-instance-attributes
        DataFrameFactory[PeaksDict]
):
    """
    Transform a `PeaksDict` to one or more `pandas.DataFrame`.

    # Default Columns

    * *peakposition*
    * *status*: whether the peak is detected as a baseline or singlestrand
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

    Should one use `dfevents` as a keyword instead, then all events related data
    will be stored in dataframes inside an *events* column.
    """
    def __init__(self, task, buffers, frame, **kwa):
        super().__init__(task, buffers, frame)

        self.__prob   = peakprobability(frame)
        meas          = dict(task.measures)
        meas.update(kwa)
        meas.update({i: i for i, j in meas.items() if j is True and 'events' not in i})
        for i, j in tuple(meas.items()):
            if j is False:
                meas.pop(i)

        self.__peakstatus = PeakStatusComputer(
            *(meas.get(i, True) for i in ('baseline', 'singlestrand'))
        )
        if {self.__peakstatus.baseline, self.__peakstatus.singlestrand} == {None}:
            self.__peakstatus = None

        self.__hfsigma  = (
            meas['hfsigma'] if isinstance(meas.get('hfsigma', None), str) else
            'hfsigma'       if meas.get('hfsigma', False) else
            ''
        )
        meas.pop('hfsigma', None)
        self.__events   = meas.pop('events', meas.get('dfevents', None))
        self.__dfevents = meas.pop('dfevents', False) and self.__events
        if self.__events is True:
            self.__events = dict()

        if self.__events is not None:
            self.__events        = {i: self.getfunction(j) for i, j in self.__events.items()}
            self.__events['avg'] = np.nanmean

        def add(verif):
            "add a measure"
            return [(i, meas.pop(i)) for i in tuple(meas) if verif(meas[i])]

        def isprop(i):
            "whether the arg is a property in the 'Probability' class"
            return (
                isinstance(i, str)
                and isinstance(getattr(Probability, i, None), property)
            )

        def ismeth(i):
            "whether the arg is a method in the 'Probability' class"
            return (
                isinstance(i, str)
                and callable(getattr(Probability, i, None))
            )

        def isnp(i):
            "whether the arg is a method in the 'numy'"
            return (
                (isinstance(i, str) and hasattr(np, i))
                or callable(i) and getattr(np, i.__name__, None) is i
            )

        def method(i):
            "return a method for measuring a value in 'Probability'"
            return partial(lambda j, k: j(k[1]), getattr(Probability, i))

        self.__attrs  = ([('hybridisationrate', 'hybridisationrate'),
                          ('averageduration',   'averageduration'),
                          ('eventcount',        'nevents')]
                         + add(isprop))
        self.__np     = [(i, self.getfunction(j)) for i, j in add(isnp)]
        self.__aggs   = [(i, tuple(self.getfunction(k) for k in j))
                         for i, j in add(lambda x: isinstance(x, tuple))]
        self.__calls: List[Tuple[str, Callable]]  = (
            [('peakposition', lambda i: i[0])]
            + add(callable)
            + [(cast(str, i), cast(Callable, method(j))) for i, j in add(ismeth)]
        )
        if any(j is not None for j in meas.values()):
            raise ValueError(f'Unrecognized measures {meas}')

    def discardcolumns(self, *args) -> 'PeaksDataFrameFactory':
        "discard some columns"
        self.__attrs  = [i for i in self.__attrs if i[0] not in args]
        self.__np     = [i for i in self.__np    if i[0] not in args]
        self.__aggs   = [i for i in self.__aggs  if i[0] not in args]
        self.__calls  = [i for i in self.__calls if i[0] not in args]
        return self

    # pylint: disable=arguments-differ
    def _run(self, frame, bead, apeaks) -> Dict[str, np.ndarray]:
        peaks  = cast(Tuple[Tuple[float, np.ndarray], ...], tuple(apeaks))
        meas: Dict[str,np.ndarray] = {}
        if self.__events:
            self.__eventmeasure(meas, peaks)

        if self.__events and not self.__dfevents:
            counts = np.array([sum(len(j) > 0 for j in i) for _, i in peaks])
        else:
            counts = np.ones(len(peaks), dtype = 'i4')

        if self.__hfsigma:
            meas['hfsigma'] = np.full(sum(counts), frame.track.rawprecision(bead), dtype = 'f4')
        if self.__peakstatus:
            status         = self.__peakstatus(frame, bead, apeaks)
            if len(status):
                meas['status'] = np.concatenate([
                    np.full(i, j, dtype = status.dtype) for i, j in zip(counts, status)
                ])
            else:
                meas['status'] = []

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
        probs = [self.__prob(i) for _, i in peaks]
        meas.update(
            {
                i: self.__peakmeasure(
                    probs,
                    counts,
                    partial(lambda attr, obj: getattr(obj, attr), j)
                )
                for i, j in self.__attrs
            })

    def __npmeasure(self, meas, peaks, counts):
        curr: List[List[np.ndarray]] = [[] for _ in self.__np]
        for cnt, (_, pks) in zip(counts, peaks):
            tmp = [np.concatenate(i['data']) for i in pks if len(i)]
            arr = np.concatenate(tmp) if len(tmp) else np.empty(0, dtype = 'f4')
            for i, (_, j) in zip(curr, self.__np):
                i.append(np.full(cnt, j(arr)))

        if len(next(iter(curr), ())):
            meas.update({i: np.concatenate(j) for (i, _), j in zip(self.__np, curr)})

    def __aggmeasure(self, meas, peaks, counts):
        curr: List[List[np.ndarray]] = [[] for _ in self.__aggs]
        for cnt, (_, pks) in zip(counts, peaks):
            arrs = [np.concatenate(i['data']) for i in pks if len(i)]

            for i, (_, (agg, point)) in zip(curr, self.__aggs):
                i.append(np.full(cnt, agg([point(i) for i in arrs])))

        if len(next(iter(curr), ())):
            meas.update({i: np.concatenate(j) for (i, _), j in zip(self.__aggs, curr)})

    def __eventmeasure(self, meas, peaks):
        tmp: Dict[str, List[np.ndarray]] = {i: [] for i in self.__events.keys()}
        tmp.update(cycle = [], start = [], length = [])

        def _append(name: str, data: Iterable):
            tmp[name].append(np.array(list(data)))

        for _, pks in peaks:
            _append('cycle',  (i for i, j in enumerate(pks) if len(j)))
            _append(
                'length',
                (
                    j['start'][-1]+len(j['data'][-1]) - j['start'][0]
                    for j in pks if len(j)
                )
            )
            _append('start',  (j['start'][0]  for j in pks if len(j)))

            arrs = tuple(np.concatenate(j['data']) for j in pks if len(j))
            for name, fcn in self.__events.items():
                _append(name, (fcn(i) for i in arrs))

        if len(next(iter(tmp.values()), ())):
            meas.update({i: np.concatenate(j) for i, j in tmp.items()})

        if self.__dfevents:
            self.__todfmeasure(meas, peaks)

    @staticmethod
    def __peakmeasure(peaks, cnt, fcn):
        tmp = [np.full(cnt[i], fcn(j)) for i, j in enumerate(peaks)]
        return np.concatenate(tmp) if tmp else np.empty(0, dtype = 'f4')

    def __todfmeasure(self, meas, peaks):
        evts = {
            i: meas.pop(i)
            for i in set(meas) & (set(self.__events) | {'cycle', 'start', 'length'})
        }
        meas['events'] = np.empty(len(peaks), dtype = 'O')
        ix1 = 0
        for ind, (pos, data) in enumerate(peaks):
            ix2 = ix1 + len(data)
            meas['events'][ind] = (
                pd.DataFrame({i: j[ix1:ix2] for i, j in evts.items()})
                .assign(peakposition = pos)
            )
            ix1 = ix2
