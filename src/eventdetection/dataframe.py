#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                      import Dict
import numpy  as np
from   control.processor.dataframe import DataFrameFactory
from   .data                       import Events, EventsArray

class EventsDataFrameFactory(DataFrameFactory[Events]):
    """
    converts to a pandas dataframe.

    Default columns are:

        * *event*: event number in the cycle
        * *start*: event start position in phase 5
        * *length*: event length
        * *avg*: event average position

    It's possible to compute and return values on all events of a cycle using:

        >>> def myfunction(evts: EventsArray) -> np.ndarray:
            ...
        >>> DataFrameTask(integral = myfunction)
    """
    def __init__(self, task, frame):
        super().__init__(task, frame)
        self.__meas           = dict(self.getfunctions())
        self.__meas['avg']    = np.nanmean
        self.__meas['length'] = len
        self.__cums           = self.__meas.pop('integral', {})

    # pylint: disable=arguments-differ
    def _run(self, _1, _2, events: EventsArray) -> Dict[str, np.ndarray]:
        return dict(event  = np.arange(len(events), dtype = 'i4'),
                    start  = events['start'],
                    **{name: np.array([fcn(i) for i in events['data']])
                       for name, fcn in self.__meas.items()},
                    **{name: np.array(fcn(events))
                       for name, fcn in self.__cums.items()}
                   )
