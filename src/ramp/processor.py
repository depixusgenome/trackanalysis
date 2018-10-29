#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create dataframe containing ramp info
"""
from   functools         import partial
from   typing            import (NamedTuple, Callable, Union, Tuple, Dict, Any,
                                 Optional, Sequence, cast)
import numpy             as np
import pandas            as pd

from   control.processor import Processor, ProcessorException
from   model             import Task, Level
from   signalfilter      import nanhfsigma
from   utils             import initdefaults

class RampDataFrameTask(Task):
    """
    Extract open/close information from each cycle and return a pd.DataFrame
    """
    level       = Level.bead
    scale       = 10.0
    percentiles = 25., 75.
    extension   = .05, .4, 1.5
    hfsigma     = 1.e-4, 5.e-3

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class RampAverageZTask(Task):
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

class RampCycleTuple(NamedTuple): # pylint: disable=missing-docstring
    bead            : int
    cycle           : int
    zmagcorrelation : float
    extent          : float
    iopen           : int
    zmagopen        : float
    iclose          : int
    zmagclose       : float
    hfsigma         : float

class RampDataFrameProcessor(Processor[RampDataFrameTask]):
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
    def status(cls, data, task: Optional[RampDataFrameTask]= None, **kwa) -> pd.DataFrame:
        "return a frame with a new status"
        if isinstance(task, RampDataFrameTask):
            tsk = task
            assert len(kwa) == 0
        else:
            tsk = cast(RampDataFrameTask, cast(type, cls.tasktype)(**kwa))

        data.set_index(["bead", "cycle"], inplace = True)
        frame = data[["extent", "hfsigma"]].groupby(level = 0).median().dropna()
        good  = (frame.hfsigma > tsk.hfsigma[0]) & (frame.hfsigma < tsk.hfsigma[1])
        frame["status"] = ["bad"] * len(frame)
        frame.loc[(frame.extent    > tsk.extension[1])
                  & (frame.extent  < tsk.extension[2])
                  & good, "status"] = "ok"
        frame.loc[(frame.extent    > tsk.extension[0])
                  & (frame.extent  <= tsk.extension[1])
                  & good, "status"] = "fixed"

        if "status" in data.columns:
            data.pop("status")
        data = data.join(frame[["status"]])
        data.reset_index(inplace = True)
        return data

    @classmethod
    def dataframe(cls, frame, **kwa) -> pd.DataFrame:
        "return all data from a frame"
        # pylint: disable=not-callable
        task  = cast(RampDataFrameTask, cast(type, cls.tasktype)(**kwa))
        lst   = []
        frame = frame[...,...]
        for i in frame.keys():
            try:
                lst.append(cls._row(task, frame, (i, frame[i])))
            except ProcessorException:
                continue
        fields = getattr(RampCycleTuple, '_fields')
        data   = pd.DataFrame({j: [k[i] for k in lst] for i,j in enumerate(fields)})
        return cls.status(data, task)

    @classmethod
    def _row(cls, task, frame, info):
        dzdt         = np.copy(info[1])
        dzdt[1:-1]   = dzdt[2:] - dzdt[:-2]
        dzdt[[0,-1]] = np.NaN

        quants               = np.nanpercentile(dzdt, task.percentiles)
        dzdt[np.isnan(dzdt)] = 0.
        rng    = task.scale*(quants[1]-quants[0])
        outl   = np.logical_or(dzdt > quants[1]+rng, dzdt < quants[0]-rng)
        zmag   = frame.track.secondaries.zmag[frame.phase(info[0][1], 0):][:len(dzdt)]

        tmp            = np.nonzero(outl & (dzdt > 0))[0]
        iopen, zopen   = (tmp[-1], zmag[tmp[-1]]) if len(tmp) else (np.NaN, np.NaN)
        tmp            = np.nonzero(outl & (dzdt < 0))[0]
        iclose, zclose = (tmp[0], zmag[tmp[0]])   if len(tmp) else (np.NaN, np.NaN)
        return RampCycleTuple(info[0][0], info[0][1],
                              pd.Series(info[1]).corr(pd.Series(zmag)),
                              np.nanmax(info[1])- np.nanmin(info[1]),
                              iopen,  zopen,
                              iclose, zclose,
                              nanhfsigma(info[1]))

class RampAverageZProcessor(Processor[RampAverageZTask]):
    """
    Creates an average bead
    """
    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        task = cast(RampAverageZTask, cast(type, cls.tasktype)(**kwa))
        fcn  = partial(cls._apply, task)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates the frames"
        args.apply(self.apply(**self.config()))

    @classmethod
    def dataframe(cls, frame, **kwa) -> pd.DataFrame:
        "return all data from a frame"
        task  = cast(RampAverageZTask, cast(type, cls.tasktype)(**kwa))
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

        fcn   = RampAverageZTask().getaction(action)
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
