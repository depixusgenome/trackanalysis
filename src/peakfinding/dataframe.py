#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                 import Dict
import numpy                  as     np

from   model                  import PHASE
from   control.processor.base import DataFrameProcessor
from   .probabilities         import Probability
from   .data                  import PeaksDict

@DataFrameProcessor.factory(PeaksDict)
def dataframe(task, frame, _, peaks) -> Dict[str, np.ndarray]:
    """
    converts to a pandas dataframe.

    Columns are:

        * *peakposition*
        * *averageduration*
        * *hybridizationrate*
        * *eventcount*
    """
    peaks = tuple(peaks)
    meas  = [('peakposition', np.array([i for i, _ in peaks]))]
    meas += [(i, np.array([j(k) for k in peaks]))
             for i, j in task.measures.items() if callable(j)]

    prob  = Probability(minduration = frame.eventsdetectionconfig.events.select.minduration,
                        framerate   = frame.track.framerate)
    ends  = frame.track.phaseduration(..., PHASE.measure)
    peaks = [prob(i, ends) for _, i in peaks]
    meas  = [(i, np.array([getattr(k, j) for k in peaks]))
             for i, j in task.measures.items() if isinstance(j, str)]
    meas += [(i, np.array([getattr(k, i) for k in peaks]))
             for i in ('hybridizationrate', 'averageduration')]
    meas.append(('eventcount', np.array([i.nevents for i in peaks])))
    return dict(meas)
