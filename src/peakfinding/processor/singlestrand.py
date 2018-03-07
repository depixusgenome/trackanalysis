#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find the peak corresponding to a single strand DNA
"""

from   typing             import List, TYPE_CHECKING, Sequence, Tuple, cast
from   functools          import partial

import numpy                  as np

from   utils              import initdefaults
from   model.task         import Task
from   model.level        import PHASE, Level
from   data.views         import Beads, Cycles, BEADKEY
from   control.processor  import Processor
if TYPE_CHECKING:
    from peakfinding.processor.selector import (PeaksDict, # pylint: disable=unused-import
                                                Output, PeakOutput)

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
    def nonclosingramps(self, frame:'PeaksDict', beadid:BEADKEY) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        delta = self.task.delta
        return [i[1] for i, j in self.__ramp(frame, beadid) if np.all(np.diff(j) > delta)]

    def closingramps(self, frame:'PeaksDict', beadid:BEADKEY) -> List[int]:
        "return the cycle indexes for which `PHASE.rampdown` has a break"
        delta = self.task.delta
        return [i[1] for i, j in self.__ramp(frame, beadid) if np.any(np.diff(j) <= delta)]

    def nonclosingevents(self, cycles:List[int], peaks: Sequence['PeakOutput']) -> List[List[int]]:
        """
        Return the cycle indexes for which `PHASE.rampdown` has no break and an
        event is detected `eventstart` frames within `PHASE.measure`
        """
        if len(peaks) == 0:
            return []

        start = self.task.eventstart
        types = (tuple, np.void)
        def _good(evt):
            return (evt is not None
                    and (evt if isinstance(evt, types) else evt[0])[0] < start)
        return [[i for i in cycles if _good(peak[i])] for _, peak in peaks]

    def singlestrandpeakindex(self,
                              frame: 'PeaksDict',
                              beadid: BEADKEY,
                              peaks:  Sequence['PeakOutput']) -> int:
        """
        Removes the single strand peak if detected
        """
        cycles = self.nonclosingramps(frame, beadid)
        if len(cycles) < 1 or len(peaks) < 1:
            return len(peaks)

        ratio  = self.task.percentage*1e-2
        ssevts = self.nonclosingevents(cycles, peaks)
        sspeak = (i for i in range(len(peaks))
                  if sum(j is not None for j in peaks[i][1])*ratio <= len(ssevts[i]))
        return next(sspeak, len(peaks))

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

    def __ramp(self, frame:'PeaksDict', beadid:BEADKEY) -> Cycles:
        "return the cycle indexes for which `PHASE.rampdown` has no break"
        beads = cast(Beads, frame.data)
        while beads is not None and not isinstance(beads, Beads):
            beads = cast(Beads, beads.data)

        if beads is None:
            beads = frame.track.beads

        return cast(Cycles, beads[beadid,:]).withphases(self.task.phase)
