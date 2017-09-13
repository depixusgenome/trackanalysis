#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                      import Dict
import numpy  as np
from   control.processor.dataframe import DataFrameFactory
from   .data                       import Events, EventsArray

class EventsDataFrameFactory(DataFrameFactory):
    """
    converts to a pandas dataframe.

    Default columns are:

        * *event*: event number in the cycle
        * *start*: event start position in phase 5
        * *length*: event length
        * *mean*: event average position
    """
    FRAME_TYPE = Events
    def __init__(self, task, frame):
        super().__init__(task, frame)
        self.__meas           = dict(self.getfunctions())
        self.__meas['mean']   = np.nanmean
        self.__meas['length'] = len

    # pylint: disable=arguments-differ
    def _run(self, _, events: EventsArray) -> Dict[str, np.ndarray]:
        return dict(event  = np.arange(len(events), dtype = 'i4'),
                    start  = events['start'],
                    **{name: np.array([fcn(i) for i in events['data']])
                       for name, fcn in self.__meas.items()})
