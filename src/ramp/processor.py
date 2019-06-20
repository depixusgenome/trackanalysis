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
    zmagcorrelation : float
    extent          : float
    iopen           : int
    zmagopen        : float
    iclose          : int
    zmagclose       : float
    hfsigma         : float
    @classmethod
    def fields(cls) -> Tuple[str, ...]:
        "return the fields"
        return cls._fields

class RampEventTuple(NamedTuple):
    bead            : int
    cycle           : int
    zmagcorrelation : float
    extent          : float
    hfsigma         : float
    phase           : float
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
    percentiles:     Tuple[float, float, float] = (25., 50., 75.)
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
        data   = pd.DataFrame({j: [k[i] for k in lst] for i,j in enumerate(fields)})
        return self.status(data)

    def status(self, data: pd.DataFrame) -> pd.DataFrame:
        "return a frame with a new status"
        data.set_index(["bead", "cycle"], inplace = True)
        data = data.assign(fixed = (
            data.zmagopen.isna()        if 'zmagopen' in data else
            data[data.phase == self.phases[0]].groupby(level = [0, 1]).zmag.count() == 0
        ))

        frame = (data[["extent", "hfsigma", "fixed"]]
                 .dropna()
                 .groupby(level = 0)
                 .agg({"extent": "median", "hfsigma": "median",
                       "fixed": ("sum", "count")}))
        frame.columns = [i[0] if i[1] == "median" else "".join(i) for i in frame.columns]
        good  = (frame.hfsigma > self.hfsigma[0]) & (frame.hfsigma < self.hfsigma[1])
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

    def dzdt(
            self,
            frame: Union[Cycles, Beads],
            key:   Tuple[int, int],
            arr:   np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        "compute dz/dt"
        cycles       = frame[:,:] if isinstance(frame, Beads) else frame
        dzdt         = np.copy(arr)
        dzdt[1:-1]   = dzdt[2:] - dzdt[:-2]
        dzdt[[0,-1]] = np.NaN

        quants               = self.scale*np.nanpercentile(dzdt, self.percentiles)
        dzdt[np.isnan(dzdt)] = np.NaN
        inds         = [
            cycles.phase(key[1], self.phases[0]),
            cycles.phase(key[1], self.phases[0]+1),
            cycles.phase(key[1], self.phases[1]),
            cycles.phase(key[1], self.phases[1]+1)
        ]
        return (
            dzdt,
            np.nonzero(dzdt[inds[0]:inds[1]] > quants[1]+self.scale*(quants[2]-quants[1]))[0],
            np.nonzero(dzdt[inds[2]:inds[3]] < quants[0]-self.scale*(quants[1]-quants[0]))[0]
        )

    def eventstats(
            self,
            frame: Union[Cycles, Beads],
            key:   Tuple[int, int],
            arr:   np.ndarray
    ) -> Iterator[RampEventTuple]:
        "compute the info per cycle"
        frame               = frame[:,:] if isinstance(frame, Beads) else frame
        dzdt, opens, closes = self.dzdt(frame, key, arr)
        zmag                = (
            frame.track.secondaries.zmag
            [frame.phase(key[1], 0):]
            [:len(dzdt)]
        )
        info            = (
            key[0], key[1],
            pd.Series(arr).corr(pd.Series(zmag)),
            np.nanmax(arr)- np.nanmin(arr),
            nanhfsigma(arr)
        )
        yield from (RampEventTuple(*info, self.phases[0], i, arr[i], zmag[i]) for i in opens)
        yield from (RampEventTuple(*info, self.phases[1], i, arr[i], zmag[i]) for i in closes)

    def cyclestats(
            self,
            frame: Union[Cycles, Beads],
            key:   Tuple[int, int],
            arr:   np.ndarray
    ) -> RampCycleTuple:
        "compute the info per cycle"
        cycles              = frame[:,:] if isinstance(frame, Beads) else frame
        nans                = np.NaN, np.NaN
        dzdt, opens, closes = self.dzdt(cycles, key, arr)
        zmag                = (
            cycles.track.secondaries.zmag
            [cycles.phase(key[1], 0):]
            [:len(dzdt)]
        )
        iopen,  zopen       = (opens[-1], zmag[opens[-1]]) if len(opens)  else nans
        iclose, zclose      = (closes[0], zmag[closes[0]]) if len(closes) else nans
        return RampCycleTuple(
            key[0], key[1],
            pd.Series(arr).corr(pd.Series(zmag)),
            np.nanmax(arr)- np.nanmin(arr),
            iopen,  zopen,
            iclose, zclose,
            nanhfsigma(arr)
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
