#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find the peak corresponding to a single strand DNA
"""
from   dataclasses        import dataclass
from   typing             import TYPE_CHECKING, Union, Optional, List, Tuple, cast
from   functools          import partial

import numpy                  as np

from   data.track            import Track
from   data.views            import Beads, Cycles, TrackView
from   taskcontrol.processor import Processor
from   taskmodel             import Task, PHASE, Level
from   utils                 import initdefaults
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from peakfinding.processor.selector import Output
    from peakfinding.peaksarray         import PeakListArray

class SingleStrandTask(Task, zattributes = ('delta',)):
    """
    Find the peak corresponding to a single strand DNA and remove it.

    A single-strand peaks is characterized as follows:

    * In any cycle, a derivative in `PHASE.rampdown` lower than `delta` is
    considered a sign that the strand has started closing.

    * If a there are no such derivative then the event starting immediatly
    (< `eventstart` ) in `PHASE.measure` is defined as *single-strand*ed.

    * If a peak has more than `percentage` of its events as *single-strand*ed,
    then that peak is a single-strand peak. It and any other above it are
    discarded.

    :param phase: the phase to use for discovering the single-strand peak
    :param eventstart: consider only events starting a maximum of 5 frames into
    the measuring phase
    :param delta: the δz threshhold indicator of the strand starting to close
    :param percentage: the min ratio of events in the single-strand peak
    detected as non-closing.
    """
    level:         Level = Level.peak
    phase:         int   = PHASE.rampdown  # phase
    eventstart:    int   = 5
    delta:         float = -0.015
    percentage:    int   = 50
    minframes:     int   = 10

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_):
        super().__init__(**_)


_DTYPE = np.dtype([('peaks', 'f4'), ('events', 'O')])
_Track = Union[Track, TrackView]

def _topeakarray(arr):
    return arr if isinstance(arr, np.ndarray) else np.array(list(arr), dtype = _DTYPE)


class SingleStrandProcessor(Processor[SingleStrandTask]):
    """
    Find the peak corresponding to a single strand DNA and remove it
    """
    def closingindex(self, frame:_Track, beadid:int) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        delta   = self.task.delta

        def _greater(arr):
            arr  = np.diff(arr)
            good = np.where(np.isfinite(arr))[0]
            cond = np.where(arr[good] < delta)[0]
            return len(arr) if len(cond) == 0 else good[cond[0]]

        return np.array([_greater(i) for i in self.__ramp(frame, beadid).values()],
                        dtype = 'i4')

    def nonclosingramps(self, frame:_Track, beadid:int) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        delta   = self.task.delta
        minlen  = self.task.minframes

        def _greater(arr):
            if arr.size < minlen:
                return False
            arr = np.diff(arr)
            arr = arr[np.isfinite(arr)]
            return len(arr) and np.all(arr > delta)
        return [i[1] for i, j in self.__ramp(frame, beadid) if _greater(j)]

    def closingramps(self, frame: _Track, beadid:int) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has a break"
        delta  = self.task.delta
        minlen = self.task.minframes

        def _lesser(arr):
            if arr.size < minlen:
                return False
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
        good  = lambda evt: len(evt) and evt[0][0] < start  # noqa
        return [[i for i in cycles if good(peak[i])] for _, peak in peaks]

    def index(self, frame:_Track, beadid:int, peaks:'PeakListArray') -> Optional[int]:
        "Removes the single strand peak if detected"
        if not hasattr(frame, 'phaseposition') or not hasattr(peaks, '__len__'):
            # can occur in tests
            return None
        itr = self.__index(frame, beadid, peaks)
        return len(peaks) if itr is None else next(itr, len(peaks)-1)+1

    def detected(self, frame:_Track, beadid:int, peaks:'PeakListArray') -> Optional[bool]:
        """
        Return whether a singlestrand peak was detected or None when the
        information is unavailable.
        """
        track = getattr(frame, 'track', frame)
        if not hasattr(track, 'phase'):
            return None

        if track.phase.duration(..., self.task.phase).mean() < self.task.eventstart:
            return None

        itr  = self.__index(frame, beadid, peaks)
        return None if itr is None else (next(itr, None) is not None)

    def remove(self, frame:_Track, info:'Output') -> Tuple[int, np.ndarray]:
        """
        Removes the single strand peak if detected
        """
        track = getattr(frame, 'track', frame)
        if track.phase.duration(..., self.task.phase).mean() < self.task.eventstart:
            return info

        peaks = _topeakarray(info[1])
        return info[0], peaks[:self.index(frame, info[0], peaks)]

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        return (partial(cls.apply, **kwa)       if toframe is None else
                toframe.withaction(cls(**kwa).remove))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

    def __ramp(self, frame: _Track, beadid:int) -> Cycles:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        if isinstance(frame, Track):
            beads = cast(Track, frame).beads
        else:
            beads = cast(Beads, getattr(frame, 'data', None))
            while beads is not None and not isinstance(beads, Beads):
                beads = cast(Beads, getattr(beads, 'data', None))

            if beads is None:
                beads = frame.track.beads  # type: ignore

        return cast(Cycles, beads[beadid,:]).withphases(self.task.phase)

    def __index(self, frame, beadid, peaks):
        if self.task.disabled or len(peaks) < 1:
            return None
        cycles = self.nonclosingramps(frame, beadid)
        if len(cycles) < 1:
            return iter(())

        ratio  = self.task.percentage*1e-2
        ssevts = [len(i) for i in self.nonclosingevents(cycles, peaks)]
        return (i for i in range(len(peaks)-1, -1, -1)
                if sum(len(j) > 0 for j in peaks[i][1])*ratio > ssevts[i])

class BaselinePeakTask(Task, zattributes = ('maxdisttozero',)):
    """
    Find the peak corresponding to the baseline and discards it and all peaks below.

    The baseline peak is detected as follows:

    * Only consider peaks within `maxdisttozero` of the median of `PHASE.initial`
    * Only consider events reaching the end of `PHASE.measure`.
    * Consider peaks with at least 10% of cycles.
    * The lowest such of such peaks is the baseline peak
    * Any peaks below are discarded

    :param measurephase: the phase containing all events.
    :param baselinephase: the phase to use to measure the baseline position
    :param eventend: only consider events within 5 frames of the end of `PHASE.measure`.
    :param maxdisttozero: only consider peaks with such a distance from the baseline.
    :param mineventpercentage: the minimum number of events in the baseline peak
    """
    level              = Level.peak
    measurephase       = PHASE.measure
    baselinephase      = PHASE.initial
    eventend           = 5
    maxdisttozero      = .015
    mineventpercentage = 10

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_):
        super().__init__(**_)

class BaselinePeakProcessor(Processor[BaselinePeakTask]):
    "Find the peak corresponding to the baseline"
    def index(self, frame:_Track, beadid:int, peaks:'PeakListArray') -> Optional[int]:
        "Removes the single strand peak if detected"
        if not hasattr(frame, 'phaseposition') or not hasattr(peaks, '__len__'):
            # can occur in tests
            return None

        peaks = _topeakarray(peaks)
        if len(peaks) == 0:
            return None

        task     = self.task
        baseline = frame.phaseposition(task.baselinephase, beadid)
        if baseline is None:
            return None

        baseline += task.maxdisttozero
        lasts     = getattr(frame, 'track', frame).phase.duration(..., task.measurephase)
        lasts     = lasts-task.eventend
        for ind, (peak, evts) in enumerate(peaks):
            if peak > baseline:
                break

            nevts = sum(len(i) > 0 and (i[-1]['start']+len(i[-1]['data']) > j)
                        for i, j in zip(evts, lasts))
            if nevts > task.mineventpercentage*1e-2*len(evts):
                return ind
        return None

    def detected(self, frame:_Track, beadid:int, peaks:'PeakListArray') -> Optional[bool]:
        "whether there is a singlestrand peak"
        if not hasattr(frame, 'phaseposition'):
            return None
        return self.index(frame, beadid, peaks) is not None

    def remove(self, frame:_Track, info:'Output') -> Tuple[int, np.ndarray]:
        "Removes the baseline peak if detected"
        peaks = _topeakarray(info[1])
        ind   = self.index(frame, info[0], peaks)
        return (info[0], peaks if ind is None else peaks[ind+1:])

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        return (partial(cls.apply, **kwa)       if toframe is None else
                toframe.withaction(cls(**kwa).remove))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

class BaselinePeakFilterTask(BaselinePeakTask):
    """
    Find the peak corresponding to the baseline and discards all peaks below.
    """
    if __doc__ is not None:
        __doc__ = BaselinePeakTask.__doc__.replace("discards it and", "discards")

class BaselinePeakFilterProcessor(Processor[BaselinePeakFilterTask]):
    "Find the peak corresponding to the baseline"
    def index(self, frame:_Track, beadid:int, peaks:'PeakListArray') -> Optional[int]:
        "Removes the single strand peak if detected"
        return BaselinePeakProcessor(task = self.task).index(frame, beadid, peaks)

    def detected(self, frame:_Track, beadid:int, peaks:'PeakListArray') -> bool:
        "whether there is a singlestrand peak"
        return self.index(frame, beadid, peaks) is not None

    def remove(self, frame:_Track, info:'Output') -> Tuple[int, np.ndarray]:
        "Removes the baseline peak if detected"
        peaks = _topeakarray(info[1])
        ind   = BaselinePeakProcessor(self.task).index(frame, info[0], peaks)
        return (info[0], peaks if ind is None or ind == 0 else peaks[ind:])

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        return (partial(cls.apply, **kwa)       if toframe is None else
                toframe.withaction(cls(**kwa).remove))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))

@dataclass
class PeakStatusComputer:
    "creates a status vector out of a frame and a list of peaks"
    baseline:     BaselinePeakTask
    singlestrand: SingleStrandTask

    def __post_init__(self):
        if not hasattr(self, 'baseline') or self.baseline is True:
            self.baseline = BaselinePeakTask()
        elif isinstance(self.baseline, dict):
            self.baseline = BaselinePeakTask(**dict(self.baseline))

        if not hasattr(self, 'singlestrand') or self.singlestrand is True:
            self.singlestrand = SingleStrandTask()
        elif isinstance(self.singlestrand, dict):
            self.singlestrand = SingleStrandTask(**dict(self.singlestrand))

    def __call__(self, frame, bead, peaks):
        status = np.full(len(peaks), "", dtype = "<U14")
        if self.baseline:
            ind = (
                BaselinePeakProcessor(task = self.baseline)
                .index(frame, bead, peaks)
            )
            if ind is not None and 0 <= ind < len(peaks):
                status[:ind] = "< baseline"
                status[ind]  = "baseline"

        if self.singlestrand:
            ind = (
                SingleStrandProcessor(task = self.singlestrand)
                .index(frame, bead, peaks)
            )
            if ind is not None and 0 <= ind < len(peaks):
                status[ind]    = "singlestrand"
                status[ind+1:] = "> singlestrand"
        return status
