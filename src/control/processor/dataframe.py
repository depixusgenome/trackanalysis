#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    functools               import partial
from    typing                  import Callable, Dict, Union, Iterator, Tuple, cast
from    pathlib                 import Path

import  pandas                  as     pd
import  numpy                   as     np

from    model.task.dataframe    import DataFrameTask
from    data.views              import TrackView
from    .base                   import Processor

class DataFrameFactory:
    "base class for creating dataframes"
    FRAME_TYPE: type = None
    def __init__(self, task: DataFrameTask, frame: TrackView) -> None:
        self.task  = task
        self.frame = frame

    def getfunctions(self) -> Iterator[Tuple[str, Callable]]:
        "returns measures, with string changed to methods from np"
        return ((i, self.getfunction(j)) for i, j in self.task.measures.items())

    @staticmethod
    def getfunction(name: Union[Callable, str]) -> Callable:
        "returns measures, with string changed to methods from np"
        if isinstance(name, str):
            return getattr(np, f'nan{name}', getattr(np, name, None))
        return name

    @staticmethod
    def indexcolumns(cnt, key = None, frame = None) -> Dict[str, np.ndarray]:
        "adds default columns"
        res = {}
        if frame is not None:
            if frame.track.key:
                res['track'] = np.full(cnt, frame.track.key)
            elif isinstance(frame.track.path, (str, Path)):
                res['track'] = np.full(cnt, str(Path(frame.track.path).name))
            else:
                res['track'] = np.full(cnt, str(Path(frame.track.path[0]).name))

        if key is not None:
            if isinstance(key, tuple) and len(key) == 2:
                res['bead']  = np.full(cnt, key[0])
                res['cycle'] = np.full(cnt, key[1])
            elif np.isscalar(key):
                res['bead'] = np.full(cnt, key)
        return res

    @classmethod
    def create(cls, task, frame):
        "creates a dataframefactory if frame is of the right type"
        # pylint: disable=unidiomatic-typecheck
        return cls(task, frame) if type(frame) is cls.FRAME_TYPE else None

    def dataframe(self, info) -> pd.DataFrame:
        "creates a dataframe"
        data = pd.DataFrame(self._run(*info))
        inds = self.indexcolumns(len(data), info[0], self.frame)
        if len(inds):
            data = pd.concat([pd.DataFrame(inds), data], 1)

        cols = [i for i in self.task.indexes if i in data]
        if len(cols):
            data.set_index(cols, inplace = True)
        return info[0], data

    def _run(self, key, values) -> Dict[str, np.ndarray]:
        raise NotImplementedError()

class DataFrameProcessor(Processor):
    "Generates pd.DataFrames"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        task = cast(DataFrameTask, cls.tasktype(**cnf)) # pylint: disable=not-callable
        fcn  = partial(cls.__merge if task.merge else cls.__apply, task)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        args.apply(self.apply(**self.config()))

    @classmethod
    def __merge(cls, task, frame):
        return pd.concat([i for _, i in cls.__apply(task, frame)])

    @staticmethod
    def __apply(task, frame):
        for sub in DataFrameFactory.__subclasses__():
            inst = sub.create(task, frame)
            if inst is not None:
                return frame.withaction(inst.dataframe)
        raise RuntimeError(f'Could not process {type(frame)} into a pd.DataFrame')
