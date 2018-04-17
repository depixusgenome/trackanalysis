#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find the peak corresponding to a single strand DNA
"""
from   typing             import TYPE_CHECKING, Union, List, Tuple, cast
from   functools          import partial

import numpy                  as np

from   utils              import initdefaults
from   model.task         import Task
from   model.level        import PHASE, Level
from   data.track         import Track
from   data.views         import Beads, Cycles, BEADKEY, TrackView
from   control.processor  import Processor
if TYPE_CHECKING:
    from peakfinding.processor.selector import PeaksDict, Output # pylint: disable=unused-import
    from peakfinding.peaksarray         import PeakListArray     # pylint: disable=unused-import

class SingleStrandTask(Task):
    """
    Find the peak corresponding to a single strand DNA and remove it.

    A single-strand peaks is characterized as follows:

    * In any cycle, a derivate in `PHASE.rampdown` lower than `delta` is
    considered a sign that the strand has started closing.

    * If a there are no such derivate then the event starting immediatly
    (< `eventstart` ) in `PHASE.measure` is defined as *single-strand*ed.

    * If a peak has more than `percentage` of its events as *single-strand*ed,
    then that peak is a single-strand peak. It and any other above it are
    discarded.
    """
    level       = Level.peak
    phase       = PHASE.rampdown
    eventstart  = 5
    delta       = -0.015
    percentage  = 50
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_):
        super().__init__(**_)

class SingleStrandProcessor(Processor[SingleStrandTask]):
    """
    Find the peak corresponding to a single strand DNA and remove it
    """
    _DTYPE    = np.dtype([('peaks', 'f4'), ('events', 'O')])
    def closingindex(self, frame:Union[Track, TrackView], beadid:BEADKEY) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        delta   = self.task.delta
        def _greater(arr):
            arr  = np.diff(arr)
            good = np.where(np.isfinite(arr))[0]
            cond = np.where(arr[good] < delta)[0]
            return len(arr) if len(cond) == 0 else good[cond[0]]

        return np.array([_greater(i) for i in self.__ramp(frame, beadid).values()],
                        dtype = 'i4')

    def nonclosingramps(self, frame:Union[Track, TrackView], beadid:BEADKEY) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        delta   = self.task.delta
        def _greater(arr):
            arr = np.diff(arr)
            arr = arr[np.isfinite(arr)]
            return len(arr) and np.all(arr > delta)
        return [i[1] for i, j in self.__ramp(frame, beadid) if _greater(j)]

    def closingramps(self, frame: Union[Track, TrackView], beadid:BEADKEY) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has a break"
        delta  = self.task.delta
        def _lesser(arr):
            arr = np.diff(arr)
            arr = arr[np.isfinite(arr)]
            return len(arr) and np.any(arr <= delta)
        return [i[1] for i, j in self.__ramp(frame, beadid) if _lesser(j)]

    def nonclosingevents(self, cycles:List[int], peaks: 'PeakListArray') -> List[List[int]]:
        """
        Return the cycle indexes for which `PHASE.rampdown` has no break and an
        event is detected `eventstart` frames within `PHASE.measure`
        """
        if len(peaks) == 0:
            return []

        start = self.task.eventstart
        good  = lambda evt: len(evt) and evt[0][0] < start
        return [[i for i in cycles if good(peak[i])] for _, peak in peaks]

    def singlestrandpeakindex(self,
                              frame: 'PeaksDict',
                              beadid: BEADKEY,
                              peaks:  'PeakListArray') -> int:
        """
        Removes the single strand peak if detected
        """
        cycles = self.nonclosingramps(frame, beadid)
        if len(cycles) < 1 or len(peaks) < 1:
            return len(peaks)

        ratio  = self.task.percentage*1e-2
        ssevts = [len(i) for i in self.nonclosingevents(cycles, peaks)]
        sspeak = (i for i in range(len(peaks)-1, -1, -1)
                  if sum(len(j) > 0 for j in peaks[i][1])*ratio > ssevts[i])
        return next(sspeak, len(peaks)-1)+1

    def removesinglestrandpeak(self,
                               frame: 'PeaksDict',
                               info: 'Output') -> Tuple[BEADKEY, np.ndarray]:
        """
        Removes the single strand peak if detected
        """
        peaks  = (info[1]    if isinstance(info[1], np.ndarray) else
                  np.array(list(info[1]), dtype = self._DTYPE))
        return info[0], peaks[:self.singlestrandpeakindex(frame, info[0], peaks)]

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        return (partial(cls.apply, **kwa)       if toframe is None else
                toframe.withaction(cls(**kwa).removesinglestrandpeak))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

    def __ramp(self, frame: Union[Track, TrackView], beadid:BEADKEY) -> Cycles:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        if isinstance(frame, Track):
            beads = cast(Track, frame).beads
        else:
            beads = cast(Beads, frame.data)
            while beads is not None and not isinstance(beads, Beads):
                beads = cast(Beads, beads.data)

            if beads is None:
                beads = frame.track.beads # type: ignore

        return cast(Cycles, beads[beadid,:]).withphases(self.task.phase)
