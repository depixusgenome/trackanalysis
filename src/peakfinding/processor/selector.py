#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deals with tasks & processors for finding peaks
"""

from   typing                     import Iterable, Iterator, Tuple, Optional
from   functools                  import partial
import numpy                      as     np

from   model                      import Level, Task
from   data.views                 import BEADKEY, TaskView, Beads, isellipsis
from   control.processor.taskview import TaskViewProcessor
from   ..selector                 import PeakSelector, Output as PeakOutput, PeaksArray

class PeakSelectorTask(PeakSelector, Task):
    "Groups events per peak"
    levelin = Level.event
    levelou = Level.peak
    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    def __init__(self, **kwa):
        Task.__init__(self)
        PeakSelector.__init__(self, **kwa)

Output = Tuple[BEADKEY, Iterator[PeakOutput]]
class PeaksDict(TaskView[PeakSelectorTask,BEADKEY]):
    """
    * `withmeasure` allows computing whatever one wants on events in a peak. One
    or two functions should be provided:

        * `singles` takes a single event data as argument. This is for cycles where
        a single event was found for that peak.
        * `multiples` takes multiple events as argument. This is for cycles
        where multiple events were found for that peak. If not provided, then
        `singles` is computed over the concatenation of the data from all events.

    ### Slicing Methods

    One can iterate over a selection of cycles and beads:

        * `track.cycles[[1, 5], [2, 7]]` to beads 1 and 5 and their cycles 2 and 7
        * `track.cycles[:,:10]` to select all beads and their cycles 0 through 9
        * `track.cycles[:10,:]` to select beads 0 through 9 and all their cycles
    """
    __doc__ =  TaskView.__format_doc__(__doc__,
                                       itercode   = """
        >>> for (ibead, icycle), data in track.cycles:
        ...     assert isinstance(ibead,  int)
        ...     assert isinstance(icycle, int)
        ...     data = tuple(data)
        ...     assert all(isinstance(i, float) for i, _ in data)
        ...     assert all(isinstance(i, PeaksArray) for _, i in data)""",
                                       actioncode = """
        >>> def myfunction(frame: PeaksDict,
        ...                info: Tuple[int, Iterator[Tuple[float, PeaksArray]]],
        ...               ) -> Tuple[int, Tuple[Tuple[float, PeaksArray]]]:
        ...     data = np.array(list(info[1]))
        ...     # iterate over cycles with single events in the peak
        ...     for i in data[frame.singles(data)]:
        ...         i[1][:] *= 1.5
        ...     # iterate over cycles with multiple events in the peak
        ...     for i in data[frame.multiples(data)]:
        ...         for j in i:
        ...             j[1][:] *= 1.5
        ...     return info[0], data
        >>> peaks.withaction(myfunction)""",
                                       chaincode  = """
        >>> # Returning the number of cycle with no events in the peak
        >>> (peaks
        ...  .withphases(5)
        ...  .withsample(slice(10, 100, 2))
        ...  .withaction(lambda _, i: (i[0], sum(1 for k in i[1] if not k)))""",
                                       datadescr  = """
        Each iteration returns a tuple, indicating the bead number and the
        cycle number, and an iterator over peaks. Peak data consists in a
        average position and an array of size the number of cycles. For each
        cycle, the information is either `None` or one or more events depending 
        on how many events were detected for that peak in that cycle. Events are
        still a start position and an array of data:""",
                                       selecting  = """
        * `selecting` allows selecting specific beads:

            * `peaks.selecting(1)` selects bead 1
            * `peaks.selecting([1, 2])` selects bead 1 and 2""",
                                       views      = "peaks")
    level  = Level.peak
    def compute(self, ibead, precision: float = None) -> Iterator[PeakOutput]:
        "Computes values for one bead"
        vals = iter(i for _, i in self.data[ibead,...]) # type: ignore
        yield from self.config(vals, self._precision(ibead, precision))

    def index(self) -> 'PeaksDict':
        "Returns indexes at the same key and positions"
        return self.withaction(self.__index)

    def withmeasure(self, singles = np.nanmean, multiples = None) -> 'PeaksDict':
        "Returns a measure per events."
        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))
        return self.withaction(partial(self.__measure, singles, multiples))

    @classmethod
    def measure(cls, itm: PeaksArray, singles = np.nanmean, multiples = None) -> PeaksArray:
        "Returns a measure per events."
        if len(itm) == 0:
            return itm

        if multiples is None:
            multiples = lambda x: singles(np.concatenate(x))

        if isinstance(itm[0][1], PeaksArray):
            itm[:] = [(i, cls.__array2measure(singles, multiples, j)) for i, j in itm]
        else :
            itm[:] = cls.__array2measure(singles, multiples, itm)
        return itm

    @staticmethod
    def singles(arr: PeaksArray) -> np.ndarray:
        "returns an array indicating where single events are"
        return np.array([isinstance(i, (tuple, np.void)) for i in arr], dtype = 'bool')

    @staticmethod
    def multiples(arr: PeaksArray) -> np.ndarray:
        "returns an array indicating where single events are"
        return np.array([isinstance(i, (list, np.ndarray)) for i in arr], dtype = 'bool')

    @classmethod
    def __measure(cls, singles, multiples, _, info):
        return info[0], ((i, cls.__array2measure(singles, multiples, j)) for i, j in info[1])

    @classmethod
    def __index(cls, _, info):
        return info[0], ((i, cls.__array2range(j)) for i, j in info[1])

    @staticmethod
    def __array2measure(singles, multiples, arr):
        if arr.dtype == 'O':
            arr[:] = [None                  if i is None            else
                      singles  (i[1])       if isinstance(i, tuple) else
                      multiples(i['data'])
                      for i in arr[:]]
        else:
            arr['data'] = [singles(i) for i in arr['data']]
        return arr

    @staticmethod
    def __array2range(arr):
        if arr.dtype == 'O':
            return np.array([None                        if i is None            else
                             range(i[0], i[0]+len(i[1])) if isinstance(i, tuple) else
                             range(i[0][0], i[-1][0]+len(i[-1][1]))
                             for i in arr])
        return np.array([None                        if i is None            else
                         range(i[0], i[0]+len(i[1])) if np.isscalar(i[1][0]) else
                         range(i[0][0], i[-1][0]+len(i[-1][1]))
                         for i in arr])

    def _get_data_keys(self):
        if isinstance(self.data, self.__class__):
            return (i for i in self.data.keys() if Beads.isbead(i))
        return (i for i, _ in self.data.keys() if Beads.isbead(i))

    @staticmethod
    def _transform_ids(sel: Iterable) -> Iterator[BEADKEY]:
        for i in sel:
            if isinstance(i, tuple):
                if len(i) == 0:
                    continue
                elif len(i) == 2 and not isellipsis(i[1]):
                    raise NotImplementedError()
                elif len(i) > 2 :
                    raise KeyError(f"Unknown key {i} in PeaksDict")
                if np.isscalar(i[0]):
                    yield i[0]
                else:
                    yield from i[0]
            else:
                yield i

    def _precision(self, ibead: int, precision: Optional[float]):
        return self.config.getprecision(precision, getattr(self.data, 'track', None), ibead)

class PeakSelectorProcessor(TaskViewProcessor[PeakSelectorTask, PeaksDict, BEADKEY]):
    "Groups events per peak"
