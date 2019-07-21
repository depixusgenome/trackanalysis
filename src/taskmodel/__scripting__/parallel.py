#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Runs tasks in parallel"
from typing                 import (Union, Sequence, Type, Dict, Generator,
                                    Callable, List, cast)
from concurrent.futures     import ProcessPoolExecutor, ThreadPoolExecutor
import pickle
import pandas               as     pd

from data.views              import TrackView
from data.tracksdict         import TracksDict
from data.track              import Track
from taskcontrol.processor   import Processor, run as _runprocessors
from taskcontrol.taskcontrol import register
from ..track                 import TrackReaderTask, RootTask, Task
from .tasks                  import Tasks

class Parallel:
    "Runs tasks in parallel"
    def __init__(self, # pylint: disable=keyword-arg-before-vararg
                 roots     : Union[TracksDict, Sequence[RootTask]] = None,
                 *tasks    : Union[Tasks, Task],
                 processors: Dict[Type[Task], Type[Processor]] = None) -> None:
        self.args: List[bytes] = []
        if roots is not None:
            self.extend(roots, *tasks, processors = processors)

    def extend(self,
               roots     : Union[TracksDict, Sequence[RootTask], Sequence[Track]],
               *tasks    : Union[Tasks, Task, Processor],
               processors: Dict[Type[Task], Type[Processor]] = None) -> 'Parallel':
        "adds new jobs"
        lroots = [i if isinstance(i, RootTask) else
                  TrackReaderTask(path = i.path, key  = i.key, axis = i.axis.name)
                  for i in getattr(roots, 'values', lambda: roots)()]
        if len(lroots) == 0:
            return self

        procs     = (register(Processor if not processors else processors)
                     if not isinstance(processors, dict) else
                     processors)
        toproc    = lambda i: cast(Processor,
                                   (i if isinstance(i, Processor) else
                                    procs[type(i)](i))
                                  )
        main      = [toproc(i) for i in Tasks.tasklist(*tasks)]
        self.args+= [pickle.dumps([toproc(i)]+main) for i in lroots]
        return self

    def process(self,
                pool: Union[ProcessPoolExecutor, ThreadPoolExecutor] = None,
                endaction: Union[str, Callable] = None):
        "processes the parallel task"
        if pool is None:
            pool = ProcessPoolExecutor()

        if endaction in (pd.concat, 'concat', 'concatenate'):
            lst: List[pd.DataFrame] = []
            for i in pool.map(self.run, self.args):
                if isinstance(i, (list, tuple)):
                    lst.extend(j for j in i if j is not None)
                elif i is not None:
                    lst.append(i)
            return pd.concat(lst)

        if callable(endaction):
            return [cast(Callable, endaction)(i) for i in pool.map(self.run, self.args)]

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
