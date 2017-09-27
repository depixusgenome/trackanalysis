#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                      import (Optional, Sequence, Iterable,
                                           Dict, Iterator, Tuple, Union, cast)
import numpy                       as     np

from   utils                       import initdefaults
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

class FitToRefArray(np.ndarray):
    """
    Array with the following fields:

    * *discarded*: the number of discarded cycles
    * *params*: the stretch and bias
    """
    # pylint: disable=unused-argument
    discarded = False
    params    = (1., 0.)
    _dtype    = np.dtype([('peaks', 'f4'), ('events', 'O')])
    _order    = None
    def __new__(cls, array, **kwa):
        obj  = np.asarray(array,
                          dtype = kwa.get('dtype', cls._dtype),
                          order = kwa.get('order', cls._order)
                         ).view(cls)
        obj.discarded = kwa.get('discarded', cls.discarded)
        obj.params    = kwa.get('params',    cls.params)
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        # pylint: disable=attribute-defined-outside-init
        self.discarded = getattr(obj, 'discarded', False)
        self.params    = getattr(obj, 'params', False)

    def __reduce_ex__(self, arg):
        fcn, red, state = super().__reduce_ex__(arg)
        return fcn, red, (state, self.discarded, self.params)

    def __setstate__(self, vals):
        super().__setstate__(vals[0])
        self.discarded = vals[1] # pylint: disable=attribute-defined-outside-init
        self.params    = vals[2] # pylint: disable=attribute-defined-outside-init

class FitToReferenceTask(Task):
    "Fits a bead to a reference"
    level                  = Level.peak
    fitdata : Fitters      = dict()
    fitalg  : HistogramFit = ChiSquareHistogramFit()
    window  : float        = 10./8.8e-4
    @initdefaults(frozenset(locals()) - {'level'},
                  peaks  = lambda self, val: self.frompeaks (val),
                  events = lambda self, val: self.fromevents(val))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __scripting__(self, kwa) -> 'FitToReferenceTask':
        if 'peaks' in kwa:
            self.frompeaks(kwa['peaks'])
        elif 'events' in kwa:
            self.fromevents(kwa['events'])
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

class FitToReferenceDict(TaskView[FitToReferenceTask, BEADKEY]):
    "iterator over peaks grouped by beads"
    level = Level.bead
    def _keys(self, sel:Optional[Sequence], _: bool) -> Iterable:
        available = frozenset(self.config.fitdata)
        if sel is None:
            return super()._keys(tuple(available), True)
        return super()._keys([i for i in sel if i in available], True)

    def compute(self, key: BEADKEY) -> np.ndarray:
        "Action applied to the frame"
        fit  = self.config.fitalg
        data = FitToRefArray(list(cast(Iterator[PeakOutput], self.data[key])))
        if len(data):
            data.discarded = getattr(data[0][1], 'discarded', 0)

        if key not in self.config.fitdata:
            raise KeyError(f"Missing reference id {key} in {self}")

        data.params      = fit.optimize(self.config.fitdata[key], fit.frompeaks(data))[1:]
        stretch, bias    = data.params
        data['peaks'][:] = (data['peaks']-bias)*stretch

        for evts in data['events']:
            for _, i in evts[PeaksDict.singles(evts)]:
                i[:] = (i[:]-bias)*stretch

            for i in evts[PeaksDict.multiples(evts)]:
                i['data'][:] = [(j-bias)*stretch for j in i['data']]
        return data

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
    PREC = 5e-6
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
        cur   = np.unique(meas['peakposition'])
        pairs = _match.compute(ref, cur, frame.config.window)

        allv  = meas['peakposition']
        for i, j in pairs:
            arr[np.abs(allv - cur[j]) < self.PREC] = self.__peaks[key][i]
        return meas

    @staticmethod
    def __getpeaks(itm: FitData) -> np.ndarray:
        if isinstance(itm, tuple):
            return itm[1]
        elem = cast(HistogramData, itm)
        ipks = np.logical_and(elem.histogram[2:,  1] < elem.histogram[1:-1, 1],
                              elem.histogram[:-2, 1] < elem.histogram[1:-1, 1])
        return elem.minvalue+ipks*elem.binwidth
