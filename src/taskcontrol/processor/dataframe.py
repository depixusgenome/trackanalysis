#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    functools               import partial
from    typing                  import (Generic, TypeVar, Callable, Dict, Any,
                                        Union, Type, Iterator, Tuple, Optional, cast)

import  pandas                  as     pd
import  numpy                   as     np

from    data.track              import Track
from    data.trackops           import trackname
from    data.views              import TrackView
from    taskmodel.dataframe     import DataFrameTask
from    utils.inspection        import parametercount
from    .base                   import Processor, ProcessorException

Frame = TypeVar('Frame', bound = TrackView)
class DataFrameFactory(Generic[Frame]):
    "base class for creating dataframes"
    def __init__(self, task: DataFrameTask, buffers, _) -> None:
        self.task      = task
        transf         = list(self.task.transform)  if self.task.transform else []
        self.transform = [(parametercount(i), i) for i in transf]
        self.tasklist  = list(buffers.model)

    @staticmethod
    def adddoc(newcls):
        "Adds the doc to the task"
        if not getattr(newcls, '__doc__', None):
            return newcls

        tpe = newcls.frametype()
        doc = '\n'.join((newcls.__doc__).split('\n')[2:]).replace('#', '##')
        DataFrameTask.__doc__ += f'\n    # For `{tpe.__module__}.{tpe.__qualname__}`\n'
        DataFrameTask.__doc__ += doc

        return newcls

    @classmethod
    def frametype(cls) -> Type[Frame]:
        "returns the frame type"
        return getattr(cls, '__orig_bases__')[0].__args__[0]

    def getfunctions(self) -> Iterator[Tuple[str, Callable]]:
        "returns measures, with string changed to methods from np"
        itr = ((i, self.getfunction(cast(str, j))) for i, j in self.task.measures.items())
        return (i for i in itr if i[1])

    @staticmethod
    def getfunction(name: Union[Callable, str]) -> Callable:
        "returns measures, with string changed to methods from np"
        if isinstance(name, str):
            return getattr(np, f'nan{name}', getattr(np, name, None))
        return name if callable(name) else None

    @staticmethod
    def trackname(track:Track) -> str:
        "returns data track name"
        return trackname(track)

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

    def dictionary(self, frame, info) -> Dict[str, np.ndarray]:
        "creates a dataframe"
        return self._run(frame, *info)

    def dataframe(self, frame, info) -> Tuple[Any, pd.DataFrame]:
        "creates a dataframe"
        data = pd.DataFrame(self._run(frame, *info))
        inds = self.indexcolumns(len(data), info[0], frame)
        if len(inds):
            data = pd.concat([pd.DataFrame(inds), data], 1, sort = False)

        for cnt, fcn in self.transform:
            if cnt == 2:
                itm = fcn(frame, info, data)
                if itm is not None:
                    data = itm
                    assert isinstance(data, pd.DataFrame)

        return info[0], data if self.task.merge else self.defaulttransform(frame, data)

    def _run(self, frame, key, values) -> Dict[str, np.ndarray]:
        raise NotImplementedError()

    def defaulttransform(self, frame, data: pd.DataFrame) -> pd.DataFrame:
        "default transform action"
        for col in ('bead', 'cycle'):
            if col not in data or data[col].dtype == np.int64:
                continue

            if np.issubdtype(data[col].dtype, np.int64):
                data[col] = data[col].astype(np.int64)
            else:
                try:
                    data[col] = np.round(data[col]).astype(np.int64)
                except ValueError:
                    pass

        if 'track' in data and hasattr(frame.track, 'pathinfo'):
            data['modification'] = frame.track.pathinfo.modification

        for cnt, fcn in self.transform:
            self.addtasklist(data)
            itm = fcn(data) if cnt == 1 else fcn(frame, data) if cnt == 2 else None
            if itm is not None:
                data = itm
                assert isinstance(data, pd.DataFrame)

        cols = [i for i in self.task.indexes if i in data]
        if len(cols):
            data.set_index(cols, inplace = True)

        self.addtasklist(data)
        return data

    def addtasklist(self, data: pd.DataFrame):
        "adds the tasklist to the dataframe"
        data.__dict__['tasklist'] = self.tasklist
        if 'tasklist' not in getattr(data, '_metadata'):
            getattr(data, '_metadata').append('tasklist')

    @classmethod
    def create(cls, task, buffers, frame):
        "creates itself"
        return cls(task, buffers, frame)

    def apply(self, frame):
        "applies itself to the frame"
        return frame.withaction(self.dataframe)

class SafeDataFrameProcessor(Processor[DataFrameTask]):
    """
    Generates pd.DataFrames

    If frames are merged, computations raising a `ProcessorException` are silently
    discarded.
    """
    @classmethod
    def apply(cls, toframe = None, buffers = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        task = cast(DataFrameTask, cls.tasktype(**cnf))  # pylint: disable=not-callable
        fcn  = partial(cls._merge if task.merge else cls._apply, task, buffers)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates the frames"
        args.apply(self.apply(**self.config(), buffers = args.data))

    @classmethod
    def _merge(cls, task, buffers, frame):
        factory = cls.factory(frame).create(task, buffers, frame)
        frame   = factory.apply(frame)
        lst     = cls._merge_list(frame)
        if not lst:
            data = pd.DataFrame()
            factory.addtasklist(data)
            return data

        return factory.defaulttransform(frame, pd.concat(lst, sort = False))

    @staticmethod
    def _merge_list(frame):
        lst = []
        if callable(getattr(frame, 'bead', None)):
            for i in {j for j, _ in frame.keys()}:
                itr = None
                try:
                    itr = iter(frame.bead(i))
                except ProcessorException:
                    continue

                while True:
                    try:
                        lst.append(next(itr)[-1])
                    except ProcessorException:
                        continue
                    except StopIteration:
                        break
        else:
            for i in frame.keys():
                try:
                    lst.append(frame[i])
                except ProcessorException:
                    continue
        return lst

    @staticmethod
    def __iter_subclasses() -> Iterator[type]:
        rem = [DataFrameFactory]
        while len(rem):
            cur = rem.pop()
            if not getattr(cur, '__abstractmethods__', None):
                yield cur
            rem.extend(i for i in cur.__subclasses__() if issubclass(i, DataFrameFactory))

    @classmethod
    def factory(cls, frame) -> Optional[Type[DataFrameFactory]]:
        "returns the appropriate factory"
        if not isinstance(frame, type):
            frame = type(frame)

        return next((i for i in cls.__iter_subclasses()
                     if frame is cast(Any, i).frametype()), None)

    @classmethod
    def _apply(cls, task, buffers, frame):
        frametype = type(frame)
        for sub in cls.__iter_subclasses():
            if frametype is cast(Any, sub).frametype():
                factory = sub.create(task, buffers, frame)
                if factory is not None:
                    out = factory.apply(frame)
                    if out is not None:
                        return out
        raise RuntimeError(f'Could not process {type(frame)} into a pd.DataFrame')

class DataFrameProcessor(SafeDataFrameProcessor):
    """
    Generates pd.DataFrames

    Exceptions are *not* silently ignored.
    """
    @staticmethod
    def _merge_list(frame):
        if callable(getattr(frame, 'bead', None)):
            keys = {i for i, _ in frame.keys()}
            return [j[-1] for i in keys for j in frame.bead(i)]
        return [i[-1] for i in frame]
