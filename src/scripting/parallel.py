#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs tasks in parallel"
from typing                 import (Union, Sequence, Type, Dict, Generator,
                                    Callable, Iterator, List, cast)
from concurrent.futures     import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing        import cpu_count
import pickle
import pandas               as     pd

from model.task.track       import TrackReaderTask, RootTask, Task
from control.taskcontrol    import register
from control.processor      import Processor, run as _runprocessors
from data.views             import TrackView
from data.tracksdict        import TracksDict

class Parallel:
    "Runs tasks in parallel"
    def __init__(self,
                 roots     : Union[TracksDict, Sequence[RootTask]] = None,
                 *tasks    : Task,
                 processors: Dict[Type[Task], Type[Processor]] = None) -> None:
        self.args: List[bytes] = []
        if roots is not None:
            self.extend(roots, *tasks, processors)

    def extend(self,
               roots     : Union[TracksDict, Sequence[RootTask]],
               *tasks    : Task,
               processors: Dict[Type[Task], Type[Processor]] = None) -> 'Parallel':
        "adds new jobs"
        if not isinstance(roots, TracksDict):
            lroots = list(cast(Iterator[RootTask], roots))
        else:
            lroots = [TrackReaderTask(path = i.path, key  = i.key, axis = i.axis.value)
                      for i in cast(TracksDict, roots).values()]

        procs     = (register(Processor if not processors else processors)
                     if not isinstance(processors, dict) else
                     processors)
        toproc    = lambda i: cast(Processor,
                                   (i if isinstance(i, Processor) else
                                    procs[type(i)](i))
                                  )
        main      = [toproc(i) for i in tasks]
        self.args+= [pickle.dumps([toproc(i)]+main) for i in lroots]
        return self

    def process(self,
                pool: Union[ProcessPoolExecutor, ThreadPoolExecutor] = None,
                endaction: Union[str, Callable] = None):
        "processes the parallel task"
        if pool is None:
            pool = ProcessPoolExecutor(cpu_count())

        if endaction in (pd.concat, 'concat', 'concatenate'):
            return pd.concat(sum((list(i) for i in pool.map(self.run, self.args)), []))

        elif callable(endaction):
            return [cast(Callable, endaction)(i) for i in pool.map(self.run, self.args)]

        else:
            res = [i for i in pool.map(self.run, self.args)]
            if all(len(i) == 1 for i in res):
                return [i[0] for i in res]
            return res

    @staticmethod
    def run(args: bytes):
        "runs one task"
        def _cnv(res):
            if isinstance(res, TrackView):
                res = tuple(res)
                if len(res) and len(res[0]) == 2 and isinstance(res[0][1], Generator):
                    res = tuple((i, tuple(j)) for i, j in res)
            return res

        return tuple(_cnv(i) for i in _runprocessors(args))

def parallel(roots     : Union[TracksDict, Sequence[RootTask]],
             *tasks    : Task,
             processors: Dict[Type[Task], Type[Processor]]              = None,
             pool      : Union[ProcessPoolExecutor, ThreadPoolExecutor] = None,
             endaction : Union[str, Callable]                           = None):
    "Runs tasks in parallel"
    return Parallel(roots, *tasks, processors = processors).process(pool, endaction)
