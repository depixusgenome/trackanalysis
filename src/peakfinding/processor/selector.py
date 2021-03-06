#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deals with tasks & processors for finding peaks
"""

from   typing                         import Optional

from   data.views                     import TaskView, Beads
from   taskcontrol.processor.taskview import TaskViewProcessor
from   taskmodel                      import Level, Task
from   ..peaksarray                   import PeakListArray
from   ..selector                     import PeakSelector

class PeakSelectorTask(PeakSelector, Task):
    """
    # Returned Values

    One pair per peak:

    1. the peak position: an average of event positions in the peak.
    2. events in the peak: an array with one entry per cycle, each cycle entry
    consisting in the events relevant the the cycle and the peak together.
    """
    if __doc__:
        __doc__ = getattr(PeakSelector, '__doc__') + __doc__

    levelin = Level.event
    levelou = Level.peak
    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    def __init__(self, **kwa):
        Task.__init__(self)
        PeakSelector.__init__(self, **kwa)

Output = PeakListArray
class PeaksDict(TaskView[PeakSelectorTask,int]): # pylint: disable=too-many-ancestors
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
        ...                info: Tuple[int, PeakListArray],
        ...               ) -> Tuple[int, PeakListArray]:
        ...     data = np.array(list(info[1]))
        ...     for i in data:
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
    # pylint: disable=arguments-differ
    def compute(self, ibead, precision: float = None) -> PeakListArray:
        "Computes values for one bead"
        vals = (self.data.bead(ibead) if hasattr(self.data, 'bead') else # type: ignore
                self.data[ibead,...].values())                           # type: ignore
        return self.config(vals, self._precision(ibead, precision))

    def beadextension(self, ibead) -> Optional[float]:
        """
        Return the median bead extension (phase 3 - phase 1)
        """
        return getattr(self.data, 'beadextension', lambda *_: None)(ibead)

    def phaseposition(self, phase: int, ibead:int) -> Optional[float]:
        """
        Return the median position for a given phase
        """
        return getattr(self.data, 'phaseposition', lambda *_: None)(phase, ibead)

    @classmethod
    def _transform_ids(cls, sel):
        return cls._transform_to_bead_ids(sel)

    def _get_data_keys(self):
        if isinstance(self.data, PeaksDict):
            return (i for i in self.data.keys() if Beads.isbead(i))
        return (i for i, _ in self.data.keys() if Beads.isbead(i))

    def _precision(self, ibead: int, precision: Optional[float]):
        return self.config.getprecision(precision, getattr(self.data, 'track', None), ibead)

class PeakSelectorProcessor(TaskViewProcessor[PeakSelectorTask, PeaksDict, int]):
    "Groups events per peak"
