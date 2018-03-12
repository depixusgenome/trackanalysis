#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Matching experimental peaks to hairpins: tasks and processors"
from   typing                           import (Optional, # pylint: disable=unused-import
                                                Iterable, Sequence, Any, Dict,
                                                Iterator, Tuple, Union, NamedTuple,
                                                List, cast)
import numpy                            as     np

from   utils                            import initdefaults
from   data.views                       import TaskView, BEADKEY
from   model.task                       import Task, Level
from   control.processor.runner         import run as _runprocessors
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

class _FitDataDescriptor:
    def __get__(self, inst, _):
        return inst.__dict__['fitdata'] if inst is not None else {}

    def __set__(self, inst, val):
        if isinstance(val, PeaksDict):
            inst.frompeaks(val)
        elif isinstance(val, Events):
            inst.fromevents(val)
        elif isinstance(val, dict):
            val.update({i: FitData(j, (1., 0.)) # type: ignore
                        for i, j in cast(dict, val.items())
                        if not isinstance(j, FitData)})
            inst.__dict__['fitdata'] = val
        else:
            fcn = lambda j: (j if isinstance(j, FitData) else FitData(j, (1., 0)))
            inst.__dict__['fitdata'] = {i: fcn(j) for i, j in cast(Dict, val).items()}

class _DefaultFitData:
    def __get__(self, inst, _):
        "returns the default data"
        return inst.__dict__.get('defaultdata', None) if inst is not None else None

    def __set__(self, inst, val):
        "returns the default data"
        alg = inst.fitalg
        fcn = lambda j: (j if isinstance(j, FitData) else FitData(j, (1., 0)))
        out = fcn(alg.frompeaks(next(val.values())) if isinstance(val, PeaksDict) else
                  alg.fromevents(val)               if isinstance(val, Events)    else
                  val)
        inst.__dict__['defaultdata'] = out
        return out


class FitToReferenceTask(Task):
    "Fits a bead to a reference"
    level                  = Level.peak
    defaultdata            = None
    fitdata                = cast(Fitters, _FitDataDescriptor())
    fitalg  : ReferenceFit = ChiSquareHistogramFit()
    window  : float        = 10./8.8e-4
    @initdefaults(frozenset(locals()) - {'level'},
                  peaks       = lambda self, val: self.frompeaks (val),
                  events      = lambda self, val: self.fromevents(val))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __contains__(self, itms):
        if self.defaultdata is not None:
            return True

        if isinstance(itms, str):
            return itms in self.fitdata
        if np.isscalar(itms):
            return int(itms) in self.fitdata

        return set(itms).issubset(set(self.fitdata))

    def frompeaks(self,
                  peaks: Union[PeaksDict, Iterable[Tuple[BEADKEY, PeakOutput]]],
                  update = False) -> 'FitToReferenceTask':
        "creates fit data for references from a PeaksDict"
        if not update:
            self.fitdata.clear()
        fcn  = self.fitalg.frompeaks
        info = {i: FitData(fcn(j), (1., 0.)) for i, j in cast(PeaksDict, peaks)}
        self.fitdata.update(info)
        return self

    def fromevents(self, events: Events, update = False) -> 'FitToReferenceTask':
        "creates fit data for references from a PeaksDict"
        if not update:
            self.fitdata.clear()
        fcn  = self.fitalg.fromevents
        keys = {i for i, _ in events.keys()}
        self.fitdata.update({i: fcn(cast(Events, events[i, ...])) for i in keys})
        return self

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

class FitToReferenceDict(TaskView[FitToReferenceTask, BEADKEY]):
    "iterator over peaks grouped by beads"
    level = Level.bead
    @classmethod
    def _transform_ids(cls, sel):
        return cls._transform_to_bead_ids(sel)

    def _keys(self, sel:Optional[Sequence], _: bool) -> Iterable:
        if self.config.defaultdata is not None:
            return super()._keys(sel, _)

        available = frozenset(self.config.fitdata)
        if sel is None:
            return super()._keys(tuple(available), True)
        seq = self._transform_ids(cast(Iterable, sel))
        return super()._keys([i for i in seq if i in available], True)

    def _getrefdata(self, key):
        ref = self.config.fitdata.get(key, self.config.defaultdata)
        if not isinstance(ref, (FitData, bool)):
            view  = next(_runprocessors(ref))
            if isinstance(view, PeaksDict):
                return FitData(self.config.fitalg.frompeaks(view[key]), (1., 0.))
            elif isinstance(view, Events):
                return FitData(self.config.fitalg.fromevents(view[key,...]), (1., 0.))
        return ref

    def optimize(self, key: BEADKEY, data: FitToRefArray):
        "returns stretch & bias"
        if len(data) == 0:
            return 1., 0.

        ref = self._getrefdata(key)
        if ref is True or ref.data is True:
            return 1., 0.

        fit           = self.config.fitalg
        stretch, bias = fit.optimize(ref.data, fit.frompeaks(data))[1:]
        if ref.params not in ((1., 0.), None):
            return stretch/ref.params[0], bias-ref.params[1]*ref.params[0]/stretch
        return stretch, bias

    def compute(self, key: BEADKEY) -> np.ndarray:
        "Action applied to the frame"
        data = FitToRefArray(list(cast(Iterator[PeakOutput], self.data[key])))
        if len(data):
            data.discarded = getattr(data[0][1], 'discarded', 0)

        stretch, bias    = self.optimize(key, data)
        data.params      = stretch, bias
        data['peaks'][:] = (data['peaks']-bias)*stretch

        for evts in data['events']:
            for i in evts:
                i['data'][:] = [(j-bias)*stretch for j in i['data']]
        return data

class FitToReferenceProcessor(TaskViewProcessor[FitToReferenceTask, FitToReferenceDict, BEADKEY]):
    "Changes the Z axis to fit the reference"

@DataFrameFactory.adddoc
class FitToReferenceDataFrameFactory(DataFrameFactory[FitToReferenceDict]):
    """
    Transform a `FitToReferenceDict` to one or more `pandas.DataFrame`.

    # Default Columns

    * *peakposition*
    * *averageduration*
    * *hybridisationrate*
    * *eventcount*
    * *referenceposition*: the peak position in the reference

    # Other

    One can add *stretch* and *bias* to the list by doing:

    ```python
    >>> DataFrameTask(stretch = True, bias = True)
    ```
    """
    if __doc__:
        __doc__ += ('\n'+PeaksDataFrameFactory.__doc__
                    [PeaksDataFrameFactory.__doc__.find('# Agg')-5:])
    PREC     = 5e-6
    def __init__(self, task, frame):
        get = lambda i: (i  if task.measures.get(i, False) is True else
                         '' if not task.measures.get(i, False)     else
                         task.measures.get(i, False))
        super().__init__(task, frame)
        self.__stretch = get('stretch')
        self.__bias    = get('bias')
        self.__parent  = PeaksDataFrameFactory(task, frame, stretch = None, bias = None)
        self.__peaks: Dict[BEADKEY, np.ndarray] = {i: self.__getpeaks(j)
                                                   for i, j in frame.config.fitdata.items()}

    # pylint: disable=arguments-differ
    def _run(self, frame, key, peaks) -> Dict[str, np.ndarray]:
        # pylint: disable=protected-access
        meas   = self.__parent._run(frame, key, peaks)
        arr    = np.full(len(meas['peakposition']), np.NaN, dtype = 'f4')
        meas['referenceposition'] = arr
        if self.__stretch:
            meas[self.__stretch] = np.full(len(arr), peaks.params[0], dtype = 'f4')
        if self.__bias:
            meas[self.__bias]    = np.full(len(arr), peaks.params[1], dtype = 'f4')

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
