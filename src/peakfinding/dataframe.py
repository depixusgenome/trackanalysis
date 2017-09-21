#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                      import Dict, cast
import numpy                       as     np

from   model                       import PHASE
from   data.views                  import selectparent
from   control.processor.dataframe import DataFrameFactory
from   eventdetection.data         import Events, EventDetectionConfig
from   .probabilities              import Probability
from   .data                       import PeaksDict

class PeaksDataFrameFactory(DataFrameFactory[PeaksDict]):
    """
    converts to a pandas dataframe.

    Columns are:

        * *peakposition*
        * *averageduration*
        * *hybridizationrate*
        * *eventcount*
    """
    def __init__(self, task, frame):
        super().__init__(task, frame)

        tmp   = selectparent(frame, Events)
        mdur  = (EventDetectionConfig() if tmp is None else tmp).events.select.minduration
        frate = frame.track.framerate

        self.__prob   = Probability(minduration = mdur, framerate = frate)
        self.__ends   = frame.track.phaseduration(..., PHASE.measure)

        meas          = task.measures.items()
        self.__calls  = [(i, j) for i, j in meas if callable(j)]
        self.__attrs  = ([(i, cast(str, j)) for i, j in meas if isinstance(j, str)]
                         +[('hybridizationrate', 'hybridizationrate'),
                           ('averageduration',   'averageduration'),
                           ('eventcount',        'nevents')])

    # pylint: disable=arguments-differ
    def _run(self, _1, _2, peaks) -> Dict[str, np.ndarray]:
        peaks = tuple(peaks)
        meas  = [('peakposition', np.array([i for i, _ in peaks]))]
        meas += [(i, np.array([j(k) for k in peaks])) for i, j in self.__calls]

        prob  = self.__prob
        peaks = [prob(i, self.__ends) for _, i in peaks]
        meas += [(i, np.array([getattr(k, j) for k in peaks])) for i, j in self.__attrs]
        return dict(meas)
