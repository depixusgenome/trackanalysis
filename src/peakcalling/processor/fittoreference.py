#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                           import (Optional, # pylint: disable=unused-import
                                                Iterable, Sequence, Any, Dict,
                                                Iterator, Tuple, Union, NamedTuple,
                                                cast)
import numpy                            as     np

from   utils                            import initdefaults
from   data.views                       import TaskView, BEADKEY, isellipsis
from   model.task                       import Task, Level
from   control.processor.taskview       import TaskViewProcessor
from   eventdetection.data              import Events
from   peakfinding.histogram            import HistogramData
from   peakfinding.processor.dataframe  import PeaksDataFrameFactory, DataFrameFactory
from   peakfinding.processor.selector   import PeakOutput, PeaksDict
from   ..toreference                    import ReferenceFit, ChiSquareHistogramFit
from   ..tohairpin                      import HairpinFitter
from   .._core                          import match as _match # pylint: disable=import-error

class FitData(NamedTuple): # pylint: disable=missing-docstring
    data   : Union[HistogramData, Tuple[HistogramData, np.ndarray], HairpinFitter]
    params : Tuple[float, float]

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
    _fitdata: Fitters      = dict()
    fitalg  : ReferenceFit = ChiSquareHistogramFit()
    window  : float        = 10./8.8e-4
    DEFAULTKEY             = ''
    @initdefaults(frozenset(locals()) - {'level', '_fitdata'},
                  peaks       = lambda self, val: self.frompeaks (val),
                  events      = lambda self, val: self.fromevents(val),
                  fitdata     = '_',
                  defaultdata = lambda self, val: setattr(self, 'defaultdata', val))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __scripting__(self, kwa) -> 'FitToReferenceTask':
        if 'peaks' in kwa:
            self.frompeaks(kwa['peaks'])
        elif 'events' in kwa:
            self.fromevents(kwa['events'])
        return self

    def __getstate__(self):
        info = self.__dict__.copy()
        info['fitdata'] = info.pop('_fitdata')
        return info

    def __contains__(self, itms):
        if self.DEFAULTKEY in self.fitdata:
            return True

        if isinstance(itms, (int, str)):
            return itms in self.fitdata

        return set(itms).issubset(set(self.fitdata))

    def config(self) -> Dict[str,Any]:
        "returns a deepcopy of its dict which can be safely used in generators"
        cnf = super().config()
        cnf['fitdata']  = cnf.pop('_fitdata')
        return cnf

    @property
    def fitdata(self):
        "returns the fitting data"
        return self._fitdata

    @fitdata.setter
    def fitdata(self, val: Union[PeaksDict, Events, Fitters]):
        "returns the fitting data"
        if isinstance(val, PeaksDict):
            self.frompeaks(val)
        elif isinstance(val, Events):
            self.fromevents(val)
        else:
            fcn           = lambda j: (j if isinstance(j, FitData) else
                                       FitData(j, (1., 0)))
            self._fitdata = {i: fcn(j) for i, j in cast(Dict, val).items()}

    def frompeaks(self, peaks: PeaksDict) -> 'FitToReferenceTask':
        "creates fit data for references from a PeaksDict"
        fcn           = self.fitalg.frompeaks
        self._fitdata = {i: FitData(fcn(j), (1., 0.))
                         for i, j in peaks}
        return self

    def fromevents(self, events: Events) -> 'FitToReferenceTask':
        "creates fit data for references from a PeaksDict"
        fcn           = self.fitalg.fromevents
        keys          = {i for i, _ in events.keys()}
        self._fitdata = {i: fcn(cast(Events, events[i, ...])) for i in keys}
        return self

    @property
    def defaultdata(self) -> Optional[FitData]:
        "returns the default data"
        return self._fitdata.get(self.DEFAULTKEY, None)

    @defaultdata.setter
    def defaultdata(self, val) -> Optional[FitData]:
        "returns the default data"
        fcn = lambda j: (j if isinstance(j, FitData) else FitData(j, (1., 0)))
        out = fcn(self.fitalg.frompeaks(val)  if isinstance(val, PeaksDict) else
                  self.fitalg.fromevents(val) if isinstance(val, Events)    else
                  val)
        self._fitdata[self.DEFAULTKEY] = out
        return out

    def getdata(self, key) -> FitData:
        "returns the fitdata"
        val = self._fitdata.get(key, None)
        out = val if val else self._fitdata.get(self.DEFAULTKEY, None)
        if out is None:
            raise KeyError(f"Missing {key}")
        return out

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

class FitToReferenceDict(TaskView[FitToReferenceTask, BEADKEY]):
    "iterator over peaks grouped by beads"
    level = Level.bead
    @staticmethod
    def _transform_ids(sel: Iterable) -> Iterator[BEADKEY]:
        for i in sel:
            if isinstance(i, tuple):
                if len(i) == 0:
                    continue
                elif len(i) == 2 and not isellipsis(i[1]):
                    raise NotImplementedError()
                elif len(i) > 2 :
                    raise KeyError(f"Unknown key {i} in FitToReferenceDict")
                if np.isscalar(i[0]):
                    yield i[0]
                else:
                    yield from i[0]
            else:
                yield i

    def _keys(self, sel:Optional[Sequence], _: bool) -> Iterable:
        if self.config.defaultdata:
            return super()._keys(sel, _)

        available = frozenset(self.config.fitdata) - {self.config.DEFAULTKEY}
        if sel is None:
            return super()._keys(tuple(available), True)
        seq = self._transform_ids(cast(Iterable, sel))
        return super()._keys([i for i in seq if i in available], True)

    def compute(self, key: BEADKEY) -> np.ndarray:
        "Action applied to the frame"
        fit  = self.config.fitalg
        data = FitToRefArray(list(cast(Iterator[PeakOutput], self.data[key])))
        if len(data):
            data.discarded = getattr(data[0][1], 'discarded', 0)

        if key not in self.config.fitdata:
            raise KeyError(f"Missing reference id {key} in {self}")

        ref           = self.config.getdata(key)
        stretch, bias = fit.optimize(ref.data, fit.frompeaks(data))[1:]
        if ref.params not in ((1., 0.), None):
            stretch, bias = (stretch/ref.params[0],
                             bias-ref.params[1]*ref.params[0]/stretch)

        data.params      = stretch, bias
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
        * *hybridisationrate*
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
        if isinstance(itm.data, tuple):
            return itm.data[1]
        elem = cast(HistogramData, itm.data)
        ipks = np.logical_and(elem.histogram[2:,  1] < elem.histogram[1:-1, 1],
                              elem.histogram[:-2, 1] < elem.histogram[1:-1, 1])
        return elem.minvalue+ipks*elem.binwidth
