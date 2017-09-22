#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                      import Dict, Iterator, Tuple, Union, cast
import numpy                       as     np

from   utils                       import initdefaults, EventsArray
from   data.views                  import TaskView, BEADKEY
from   model.task                  import Task, Level
from   control.processor.taskview  import TaskViewProcessor
from   eventdetection.data         import Events
from   peakfinding.histogram       import HistogramData
from   peakfinding.dataframe       import PeaksDataFrameFactory, DataFrameFactory
from   peakfinding.data            import PeakOutput, PeaksDict
from   ..toreference               import HistogramFit, ChiSquareHistogramFit
from   .._core                     import match as _match # pylint: disable=import-error

FitData = Union[HistogramData, Tuple[HistogramData, np.ndarray]]
Fitters = Dict[BEADKEY, FitData]

class FitToReferenceTask(Task):
    "Fits a bead to a reference"
    level                  = Level.peak
    fitdata : Fitters      = dict()
    fitalg  : HistogramFit = ChiSquareHistogramFit()
    window  : float        = 10./8.8e-4
    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__init_data(kwa)

    def __scripting__(self, kwa) -> 'FitToReferenceTask':
        self.__init_data(kwa)
        return self

    def frompeaks(self, peaks: PeaksDict) -> 'FitToReferenceTask':
        "creates fit data for references from a PeaksDict"
        self.fitdata = {i: self.fitalg.frompeaks(j) for i, j in peaks}
        return self

    def fromevents(self, events: Events) -> 'FitToReferenceTask':
        "creates fit data for references from a PeaksDict"
        keys = {i for i, _ in events.keys()}
        self.fitdata = {i: self.fitalg.fromevents(cast(Events, events[i, ...])) for i in keys}
        return self

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    def __init_data(self, kwa):
        if 'peaks' in kwa:
            self.frompeaks(kwa['peaks'])
        elif 'events' in kwa:
            self.fromevents(kwa['events'])

class FitToReferenceDict(TaskView[FitToReferenceTask, BEADKEY]):
    "iterator over peaks grouped by beads"
    level = Level.bead
    dtype = np.dtype([('peaks', 'f4'), ('events', 'O')])
    def compute(self, key: BEADKEY) -> np.ndarray:
        "Action applied to the frame"
        fit           = self.config.fitalg
        data          = np.array(list(cast(Iterator[PeakOutput], self.data[key])),
                                 dtype = self.dtype)
        stretch, bias = fit.optimize(self.config.fitdata[key],
                                     fit.frompeaks(data))[1:]

        data['peaks'][:] = (data['peaks']-bias)*stretch

        mult  = self.__multiple
        for evts in data['events']:
            good               = PeaksDict.singles(evts)
            evts['data'][good] = (evts['data'][good]-bias)*stretch

            good               = PeaksDict.multiples(evts)
            evts['data'][good] = [mult(i, stretch, bias) for i in evts['data'][good]]
        return data

    @staticmethod
    def __multiple(evts:EventsArray, stretch: float, bias: float) -> EventsArray:
        evts['data'] = [(i-bias)*stretch for i in evts['data']]
        return evts

class FitToReferenceProcessor(TaskViewProcessor[FitToReferenceTask, FitToReferenceDict, BEADKEY]):
    "Changes the Z axis to fit the reference"

class FitToReferenceDataFrameFactory(DataFrameFactory[FitToReferenceDict]):
    """
    converts to a pandas dataframe.

    Columns are:

        * *peakposition*
        * *averageduration*
        * *hybridizationrate*
        * *eventcount*
        * *referenceposition*: the peak position in the reference
    """
    def __init__(self, task, frame):
        super().__init__(task, frame)
        self.__parent = PeaksDataFrameFactory(task, frame)
        self.__peaks: Dict[BEADKEY, np.ndarray] = {i: self.__getpeaks(j)
                                                   for i, j in frame.config.fitdata.items()}

    # pylint: disable=arguments-differ
    def _run(self, frame, key, peaks) -> Dict[str, np.ndarray]:
        # pylint: disable=protected-access
        meas   = self.__parent._run(frame, key, peaks)
        arr    = np.full(len(meas['peakposition']), np.NaN, dtype = 'f4')
        meas['referenceposition'] = arr

        ref   = self.__peaks[key]
        cur   = meas['peakposition']
        pairs = _match.compute(ref, cur, frame.config.window)

        arr[pairs[:,1]] = self.__peaks[key][pairs[:,0]]
        return meas

    @staticmethod
    def __getpeaks(itm: FitData) -> np.ndarray:
        if isinstance(itm, tuple):
            return itm[1]
        elem = cast(HistogramData, itm)
        ipks = np.logical_and(elem.histogram[2:,  1] < elem.histogram[1:-1, 1],
                              elem.histogram[:-2, 1] < elem.histogram[1:-1, 1])
        return elem.minvalue+ipks*elem.binwidth
