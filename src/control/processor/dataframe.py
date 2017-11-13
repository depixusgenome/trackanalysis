#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    functools               import partial
from    typing                  import (Generic, TypeVar, Callable, Dict,
                                        Union, Type, Iterator, Tuple, Optional, cast)
from    pathlib                 import Path

import  pandas                  as     pd
import  numpy                   as     np

from    model.task.dataframe    import DataFrameTask
from    data.track              import Track
from    data.views              import TrackView
from    .base                   import Processor

Frame = TypeVar('Frame', bound = TrackView)
class DataFrameFactory(Generic[Frame]):
    "base class for creating dataframes"
    def __init__(self, task: DataFrameTask, _: TrackView) -> None:
        self.task  = task

    @classmethod
    def frametype(cls)-> Type[Frame]:
        "returns the frame type"
        return cls.__orig_bases__[0].__args__[0] # type: ignore

    def getfunctions(self) -> Iterator[Tuple[str, Callable]]:
        "returns measures, with string changed to methods from np"
        itr = ((i, self.getfunction(j)) for i, j in self.task.measures.items())
        return (i for i in itr if i[1])

    @staticmethod
    def getfunction(name: Union[Callable, str]) -> Callable:
        "returns measures, with string changed to methods from np"
        if isinstance(name, str):
            return getattr(np, f'nan{name}', getattr(np, name, None))
        return name if callable(name) else None

    @staticmethod
    def trackname(track:Track) -> str:
        "returns the track name"
        if track.key:
            return track.key

        path = track.path
        if isinstance(path, (str, Path)):
            return str(Path(path).name)
        return str(Path(path[0]).name)

    @classmethod
    def indexcolumns(cls, cnt, key = None, frame = None) -> Dict[str, np.ndarray]:
        "adds default columns"
        res = {}
        if frame is not None:
            res['track'] = np.full(cnt, cls.trackname(frame.track))

        if key is not None:
            if isinstance(key, tuple) and len(key) == 2:
                res['bead']  = np.full(cnt, key[0])
                res['cycle'] = np.full(cnt, key[1])
            elif np.isscalar(key):
                res['bead'] = np.full(cnt, key)
        return res

    def dataframe(self, frame, info) -> pd.DataFrame:
        "creates a dataframe"
        data = pd.DataFrame(self._run(frame, *info))
        inds = self.indexcolumns(len(data), info[0], frame)
        if len(inds):
            data = pd.concat([pd.DataFrame(inds), data], 1)

        cols = [i for i in self.task.indexes if i in data]
        if len(cols):
            data.set_index(cols, inplace = True)

        for fcn in self.task.transform if self.task.transform else []:
            itm = fcn(data)
            if itm is not None:
                data = itm
                assert isinstance(data, pd.DataFrame)
        return info[0], data

    def _run(self, frame, key, values) -> Dict[str, np.ndarray]:
        raise NotImplementedError()

class DataFrameProcessor(Processor[DataFrameTask]):
    "Generates pd.DataFrames"
    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        task = cast(DataFrameTask, cls.tasktype(**cnf)) # pylint: disable=not-callable
        fcn  = partial(cls.__merge if task.merge else cls.__apply, task)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates the frames"
        args.apply(self.apply(**self.config()))

    @classmethod
    def __merge(cls, task, frame):
        return pd.concat([i for _, i in cls.__apply(task, frame)])

    @staticmethod
    def __iter_subclasses() -> Iterator[type]:
        rem = [DataFrameFactory]
        while len(rem):
            cur = rem.pop()
            if not len(cur.__abstractmethods__): # type: ignore
                yield cur
            rem.extend(i for i in cur.__subclasses__() if issubclass(i, DataFrameFactory))

    @classmethod
    def factory(cls, frame) -> Optional[Type[DataFrameFactory]]:
        "returns the appropriate factory"
        if not isinstance(frame, type):
            frame = type(frame)

        return next((i for i in cls.__iter_subclasses() if frame is i.frametype()), None)

    @classmethod
    def __apply(cls, task, frame):
        sub = cls.factory(frame)
        if sub is not None:
            return frame.withaction(sub(task, frame).dataframe)
        raise RuntimeError(f'Could not process {type(frame)} into a pd.DataFrame')
