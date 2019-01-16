#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deals with tasks & processors for finding peaks
"""

from   typing                     import Optional, cast

from   model                      import Level, Task, PHASE
from   data                       import Track
from   data.views                 import BEADKEY, TaskView
from   control.processor.taskview import TaskViewProcessor
from   ..peaksarray               import PeakListArray
from   ..projection               import PeakProjector

class PeakProjectorTask(PeakProjector, Task):
    """
    # Returned Values

    One pair per peak:

    1. the peak position: an average of event positions in the peak.
    2. events in the peak: an array with one entry per cycle, each cycle entry
    consisting in the events relevant the the cycle and the peak together.
    """
    if __doc__:
        __doc__ = getattr(PeakProjector, '__doc__') + __doc__

    levelin = Level.event
    levelou = Level.peak
    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    def __init__(self, **kwa):
        Task.__init__(self)
        PeakProjector.__init__(self, **kwa)

Output = PeakListArray
class PeakProjectorDict(TaskView[PeakProjectorTask,BEADKEY]): # pylint: disable=too-many-ancestors
    "Groups bead frames into peaks"
    if __doc__:
        from .selector import PeaksDict
        __doc__ = getattr(PeaksDict, "__doc__", None)

    level  = Level.peak
    # pylint: disable=arguments-differ
    def compute(self, ibead, precision: float = None) -> PeakListArray:
        "Computes values for one bead"
        phase = cast(Track, self.track).phase.select
        return self.config(
            (
                cast(dict, self.data)[ibead],
                phase(..., PHASE.measure),
                phase(..., PHASE.measure+1),
            ),
            self._precision(ibead, precision)
        )

    def beadextension(self, ibead) -> Optional[float]:
        """
        Return the median bead extension (phase 3 - phase 1)
        """
        return getattr(self.data, 'beadextension', lambda *_: None)(ibead)

    def phaseposition(self, phase: int, ibead:BEADKEY) -> Optional[float]:
        """
        Return the median position for a given phase
        """
        return getattr(self.data, 'phaseposition', lambda *_: None)(phase, ibead)

    def _precision(self, ibead: int, precision: Optional[float]):
        return self.config.getprecision(precision, getattr(self.data, 'track', None), ibead)

class PeakProjectorProcessor(TaskViewProcessor[PeakProjectorTask, PeakProjectorDict, BEADKEY]):
    "Groups bead frames into peaks"
