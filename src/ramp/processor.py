#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create dataframe containing ramp info
"""
from   functools         import partial
from   typing            import (NamedTuple, Callable, Union, Tuple, Dict, Any,
                                 Optional, Sequence, Iterator, cast)
import numpy             as np
import pandas            as pd

from   data.views            import Cycles, Beads
from   signalfilter          import nanhfsigma
from   taskcontrol.processor import Processor, ProcessorException
from   taskmodel             import Task, Level
from   utils                 import initdefaults

class RampCycleTuple(NamedTuple):
    bead            : int
    cycle           : int
    population      : int
    zmagcorrelation : float
    extent          : float
    hfsigma         : float
    iopen           : int
    zmagopen        : float
    iclose          : int
    zmagclose       : float
    @classmethod
    def fields(cls) -> Tuple[str, ...]:
        "return the fields"
        return cls._fields

class RampEventTuple(NamedTuple):
    bead            : int
    cycle           : int
    population      : int
    zmagcorrelation : float
    extent          : float
    hfsigma         : float
    phase           : float
    ievent          : int
    dzdt            : float
    zbead           : float
    zmag            : float
    @classmethod
    def fields(cls) -> Tuple[str,...]:
        "return the fields"
        return cls._fields

class RampStatsTask(Task):
    """
    Extract open/close information from each cycle and return a pd.DataFrame
    """
    level                                       = Level.bead
    scale:           float                      = 10.0
    percentiles:     Tuple[float, float]        = (25., 75.)
    population:      int                        = 80
    extension:       Tuple[float, float, float] = (.05, .4, 1.5)
    hfsigma:         Tuple[float, float]        = (1.e-4, 5.e-3)
    fixedcycleratio: float                      = 90.
    events:          bool                       = False
    phases:          Tuple[int,int]             = (2, 4)

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def dataframe(self, frame) -> pd.DataFrame:
        "return all data from a frame"
        fields = RampEventTuple.fields() if self.events else RampCycleTuple.fields()
        lst    = list(self.stats(frame))
        data   = pd.DataFrame({
            j: [k[i] for k in lst] for i,j in enumerate(fields) # type: ignore
        })
        return self.status(data)

    __AGGS = {
        "extent":     "median",
        "hfsigma":    "median",
        "population": "mean",
        "fixed":      ("sum", "count")
    }

    def status(self, data: pd.DataFrame) -> pd.DataFrame:
        "return a frame with a new status"
        data.set_index(["bead", "cycle"], inplace = True)
        data = data.assign(fixed = (
            data.zmagopen.isna()        if 'zmagopen' in data else
            data[data.phase == self.phases[0]].groupby(level = [0, 1]).zmag.count() == 0
        ))

        frame = data[list(self.__AGGS)].dropna().groupby(level = 0).agg(self.__AGGS)
        frame.columns = [i[0] if i[1] in ("median", "mean") else "".join(i) for i in frame.columns]
        good  = (
            (frame.hfsigma > self.hfsigma[0])
            & (frame.hfsigma < self.hfsigma[1])
            & (frame.population > self.population)
        )
        frame["status"] = ["bad"] * len(frame)
        frame.loc[(frame.extent    > self.extension[0])
                  & (frame.extent  < self.extension[2])
                  & good, "status"] = "ok"
        frame.loc[(frame.extent  <= self.extension[1])
                  & (frame.fixedsum * 1e-2 * self.fixedcycleratio < frame.fixedcount)
                  & good, "status"] = "fixed"

        if "status" in data.columns:
            data.pop("status")
        data = data.join(frame[["status"]])
        data.reset_index(inplace = True)
        return data

    @staticmethod
    def dzdt(arr:np.ndarray) -> np.ndarray:
        "compute dz/dt"
        dzdt         = np.copy(arr)
        dzdt[1:-1]   = dzdt[2:] - dzdt[:-2]
        dzdt[[0,-1]] = np.NaN
        return dzdt

    def eventindexes(
            self,
            cycles: Cycles,
            cycle:  int,
            dzdt:   np.ndarray
    ) -> Iterator[np.ndarray]:
        "compute dz/dt events"
        for i, comp in enumerate((np.greater, np.less)):
            pha    = tuple(cycles.phase(cycle, self.phases[i]+j) for j in range(2))
            arr    = dzdt[pha[0]:pha[1]]
            if np.any(np.isfinite(arr)):
                quants = np.nanpercentile(arr, self.percentiles)
                limits = quants[1-i] + self.scale*(quants[1-i]-quants[i])

                inds   = np.nonzero(comp(arr, limits))[0] + pha[0]
                inds   = np.concatenate([inds[:1], inds[1:][np.diff(inds) > 1]])
            else:
                inds   = np.zeros(0, dtype = 'i8')
            yield inds

    def eventstats(
            self,
            frame: Union[Cycles, Beads],
            key:   Tuple[int, int],
            arr:   np.ndarray
    ) -> Iterator[RampEventTuple]:
        "compute the info per cycle"
        cycles        = frame[:,:] if isinstance(frame, Beads) else frame
        dzdt          = self.dzdt(arr)
        opens, closes = self.eventindexes(cycles, key[1], dzdt)
        zmag          = (
            cycles.track.secondaries.zmag
            [cycles.phase(key[1], 0):]
            [:len(dzdt)]
        )
        info = self.__cyclebaseinfo(key, arr, zmag)
        get  = lambda i, j: RampEventTuple( # type: ignore
            *info,
            self.phases[j], i, dzdt[i], arr[i], zmag[i]
        )
        yield from (get(i, 0) for i in opens)
        yield from (get(i, 1) for i in closes)

    def cyclestats(
            self,
            frame: Union[Cycles, Beads],
            key:   Tuple[int, int],
            arr:   np.ndarray
    ) -> RampCycleTuple:
        "compute the info per cycle"
        nans          = np.NaN, np.NaN
        cycles        = frame[:,:] if isinstance(frame, Beads) else frame
        dzdt          = self.dzdt(arr)
        opens, closes = self.eventindexes(cycles, key[1], dzdt)
        zmag          = (
            cycles.track.secondaries.zmag
            [cycles.phase(key[1], 0):]
            [:len(dzdt)]
        )
        return RampCycleTuple(                       # type: ignore
            *self.__cyclebaseinfo(key, arr, zmag),
            *((opens[-1], zmag[opens[-1]]) if len(opens)  else nans),
            *((closes[0], zmag[closes[0]]) if len(closes) else nans)
        )

    def stats(self, frame: Beads) -> Union[Iterator[RampCycleTuple], Iterator[RampEventTuple]]:
        "iterate through the rows of stats"
        cycles = frame[:,:] if isinstance(frame, Beads) else frame
        if self.events:
            for i in cycles.keys():
                try:
                    yield from self.eventstats(cycles, i, cycles[i])
                except ProcessorException:
                    continue
        else:
            for i in cycles.keys():
                try:
                    yield self.cyclestats(cycles, i, cycles[i])
                except ProcessorException:
                    continue
    @staticmethod
    def __cyclebaseinfo(
            key:  Tuple[int, int],
            arr:  np.ndarray,
            zmag: np.ndarray
    ) -> Tuple[int, int, float, float, float, float]:
        pop = np.isfinite(arr).sum()*100./max(1, len(arr))
        return (
            key[0], key[1],
            pop,
            0. if pop == 0. else pd.Series(arr).corr(pd.Series(zmag)),
            0. if pop == 0. else np.nanmax(arr)- np.nanmin(arr),
            nanhfsigma(arr)
        )

class RampConsensusBeadTask(Task):
    """
    Creates an average bead
    """
    level                                                   = Level.bead
    action: Union[Callable, str, Tuple[str, Dict[str,Any]]] = "median"
    normalize                                               = True
    phases                                                  = 0, 3, 4, 7
    @initdefaults(locals())
    def __init__(self, **_):
        super().__init__(**_)

    def getaction(self, act = None) -> Callable:
        "return the action to perform on all results"
        arg = self.action if act is None else act
        if callable(arg):
            return arg
        if isinstance(arg, str):
            return partial(getattr(np, f"nan{arg}", getattr(np, arg)), axis = 0)
        if isinstance(arg, tuple):
            fcn = getattr(np, f"nan{arg[0]}", getattr(np, arg[0]))
            return partial(fcn, **cast(dict, arg[1]), axis = 0)
        raise AttributeError("unknown numpy action")

class RampDataFrameProcessor(Processor[RampStatsTask]):
    """
    Generates pd.DataFrames

    If frames are merged, computations raising a `ProcessorException` are
    silently discarded.
    """
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        fcn  = partial(cls.dataframe, **cnf)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates the frames"
        args.apply(self.apply(**self.config()))

    @classmethod
    def dataframe(cls, frame, **kwa) -> pd.DataFrame:
        "return all data from a frame"
        return RampStatsTask(**kwa).dataframe(frame)

    @classmethod
    def status(cls, data, task: Optional[RampStatsTask]= None, **kwa) -> pd.DataFrame:
        "return a frame with a new status"
        return (
            (task if isinstance(task, RampStatsTask) else RampStatsTask(**kwa))
            .status(data)
        )

class RampConsensusBeadProcessor(Processor[RampConsensusBeadTask]):
    """
    Creates an average bead
    """
    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        task = cast(RampConsensusBeadTask, cast(type, cls.tasktype)(**kwa))
        fcn  = partial(cls._apply, task)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates the frames"
        args.apply(self.apply(**self.config()))

    @classmethod
    def dataframe(cls, frame, **kwa) -> pd.DataFrame:
        "return all data from a frame"
        task  = cast(RampConsensusBeadTask, cast(type, cls.tasktype)(**kwa))
        data  = dict(cls._apply(task, frame))
        shape = next(iter(data.values()))[1].shape

        if len(shape) > 1:
            frame = pd.DataFrame({(i, k): j[1][k,:]
                                  for i, j in data.items() for k in range(shape[0])})
        else:
            frame = pd.DataFrame({i: j[1] for i, j in data.items()})

        zmag          = next(iter(data.values()))[0]
        frame["zmag"] = zmag[shape[0]//2,:] if len(shape) > 1 else zmag
        return frame

    @classmethod
    def consensus(cls, frame, normalize, # pylint: disable=too-many-arguments
                  beads: Optional[Sequence[int]] = None,
                  name                           = "consensus",
                  action                         = "median"):
        "add a consensus bead"
        if not any(isinstance(i, int) or (isinstance(i, tuple) and isinstance(i[0], int))
                   for i in frame.columns):
            return

        fcn   = RampConsensusBeadTask().getaction(action)
        if all(isinstance(i, tuple) for i in frame.columns):
            if normalize:
                norm1 = lambda *i: frame[i].values *(100./np.nanmax(frame[i[0],1]))
            else:
                norm1 = lambda *i: frame[i]

            if beads is None:
                beads = list({i[0] for i in frame.columns if isinstance(i[0], int)})

            ind   = next(i[0] for i in frame.columns if isinstance(i[0], int))
            shape = len(frame[ind].columns)
            for i in range(shape):
                frame[name, i] = (np.NaN if len(beads) == 0 else
                                  fcn([norm1(j, i) for j in beads]))
        else:
            if normalize:
                norm = lambda i: frame[i].values *(100./np.nanmax(frame[i]))
            else:
                norm = lambda i: frame[i]
            if beads is None:
                beads = list({i for i in frame.columns if isinstance(i, int)})
            frame[name] = np.NaN if len(beads) == 0 else fcn([norm(i) for i in beads])

    @classmethod
    def _apply(cls, task, frame):
        return frame.withaction(partial(cls._average, task))

    @classmethod
    def _average(cls, task, frame, info):
        phases = frame.track.phase .select(..., list(task.phases))
        size   = min(min(j-i, l-k) for i, j, k, l in phases)
        act    = task.getaction()

        # above the max value, do *not* subtract lower signal
        vals   = [info[1][k:k+size][::-1]-info[1][i:i+size] for i, j, k, l in phases]
        for i, j in enumerate(vals):
            amax       = np.argmax(j)
            k          = phases[i, 2]
            j[amax+1:] = info[1][k+amax+1:k+size]+(j[amax]-info[1][k+amax])
        arr    = act(vals)
        if task.normalize:
            arr *= 100./np.nanmax(arr)

        zmag = frame.track.secondaries.zmag
        zmag = [(zmag[k:k+size][::-1]+zmag[i:i+size])*.5 for i, j, k, l in phases]
        return info[0], (act(zmag), arr)
