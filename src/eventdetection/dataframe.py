#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
import numpy  as np
from   control.processor.base import DataFrameProcessor
from   .data                  import Events, EventsArray

@DataFrameProcessor.factory(Events)
def dataframe(task, _1, _2, events:EventsArray) -> dict:
    """
    converts to a pandas dataframe.

    Columns are:

        * *event*: event number in the cycle
        * *start*: event start position in phase 5
        * *length*: event length
        * *mean*: event average position
    """
    meas = task.getfunctions()
    if not any(i[1] in (np.nanmean, np.mean) for i in meas):
        meas = (('mean', np.nanmean),) + meas
    if not any(i[1] is len for i in meas):
        meas = (('length', len),) + meas

    items = dict(event  = np.arange(len(events), dtype = 'i4'),
                 start  = events['start'],
                 **{name: [fcn(i) for i in events['data']] for name, fcn in meas})
    return items
