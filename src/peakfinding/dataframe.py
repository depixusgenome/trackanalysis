#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"
from   typing                      import Dict, List, cast # pylint: disable=unused-import
from   functools                   import partial
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

    One can also add information on events using:

        >> DataFrameTask(measures = dict(events = True))

    In such a case, added columns are:

    * *cycle*: event cycle
    * *start*: event start position
    * *length*: event length
    * *mean*: event average

    The following will also measure the event's std:

        >> DataFrameTask(measures = dict(events = dict(eventstd = np.nanstd)))

    or

        >> DataFrameTask(measures = dict(events = dict(eventstd = 'std')))
    """
    def __init__(self, task, frame):
        super().__init__(task, frame)

        tmp   = selectparent(frame, Events)
        mdur  = (EventDetectionConfig() if tmp is None else tmp).events.select.minduration
        frate = frame.track.framerate

        self.__prob   = Probability(minduration = mdur, framerate = frate)
        self.__ends   = frame.track.phaseduration(..., PHASE.measure)

        self.__events = task.measures.get('events', None)
        if self.__events is True:
            self.__events = dict()

        if self.__events is not None:
            self.__events         = {i: self.getfunction(j) for i, j in self.__events.items()}
            self.__events['mean'] = np.nanmean

        meas          = task.measures.items()
        self.__calls  = ([('peakposition', lambda i: i[0])]
                         +[(i, j) for i, j in meas if callable(j)])
        self.__attrs  = ([(i, cast(str, j)) for i, j in meas if isinstance(j, str)]
                         +[('hybridizationrate', 'hybridizationrate'),
                           ('averageduration',   'averageduration'),
                           ('eventcount',        'nevents')])

    # pylint: disable=arguments-differ
    def _run(self, _1, _2, peaks) -> Dict[str, np.ndarray]:
        peaks  = tuple(peaks)
        if self.__events:
            tmp   = {i: [] for i in self.__events.keys()} # type: Dict[str, List[np.ndarray]]
            tmp.update(cycle = [], start = [], length = [])

            append = lambda x, y: tmp[x].append(np.array(list(y)))
            for _, pks in peaks:
                append('cycle', (i for i, j in enumerate(pks) if j is not None))

                data = tuple((isinstance(j, (tuple, np.void)), j)
                             for i, j in enumerate(pks) if j is not None)

                append('length', ((len(j[1]) if i else
                                   j['start'][-1]+len(j['data'][-1]) - j['start'][0])
                                  for i,  j in data))
                append('start',  (j[0] if i else j['start'][0]  for i,  j in data))

                arrs = tuple((j[1] if i else np.concatenate(j['data'])) for i, j in data)
                for name, fcn in self.__events.items():
                    append(name, (fcn(i) for i in arrs))

            counts = np.array([sum(j is not None for j in i) for _, i in peaks])
            meas   = {i: np.concatenate(j) for i, j in tmp.items()}
        else:
            counts = np.ones(len(peaks), dtype = 'i4')
            meas   = {}

        meas.update({i: self.__peakmeasure(peaks, counts, j)  for i, j in self.__calls})

        prob  = self.__prob
        probs = [prob(i, self.__ends) for _, i in peaks]
        get   = lambda attr, obj: getattr(obj, attr)
        meas.update({i: self.__peakmeasure(probs, counts, partial(get, j))
                     for i, j in self.__attrs})

        return meas

    @staticmethod
    def __peakmeasure(peaks, cnt, fcn):
        return np.concatenate([np.full(cnt[i], fcn(j)) for i, j in enumerate(peaks)])
