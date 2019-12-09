#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Running jobs on all TaskCacheList"

from   multiprocessing            import Process, Pipe
from   multiprocessing.connection import Connection
from   typing                     import (
    Dict, Callable, List, Optional, Set, Union, Any, Iterator, Tuple,
    AsyncIterator, ContextManager
)
import asyncio

import pandas as pd

from data.trackio           import TrackIOError
from taskcontrol.processor  import ProcessorException
from taskmodel.dataframe    import DataFrameTask
from taskmodel.processors   import TaskCacheList
from utils.logconfig        import getLogger

LOGS  = getLogger(__name__.replace("_", ""))
STORE = Dict[int, Union[Exception, pd.DataFrame]]

class JobConfig:
    "Pool config"
    def __init__(self):
        self.name:          str   = "peakcalling.precomputations"
        self.ncpu:          int   = 2
        self.waittime:      float = .1
        self.stoptime:      float = .3
        self.maxkeysperjob: int   = 10
        self.multiprocess:  bool  = True

class JobDisplay:
    "Pool live info"
    def __init__(self):
        self.name:   str  = "peakcalling.precomputations"
        self.calls:  int  = 1
        self.active: bool = True
        self.last:   int  = 1

    @property
    def needsrefresh(self) -> bool:
        "return whether to refresh"
        return self.active and self.last < self.calls

class JobEventNames:
    """Deals with emitting job-related events"""
    def __init__(self, ctrl = None):
        self.eventname:     str = getattr(ctrl, 'eventname', 'peakcalling.view.jobs')
        self.eventjobstart: str = getattr(ctrl, 'eventjobstart', f'{self.eventname}.start')
        self.eventjobstop:  str = getattr(ctrl, 'eventjobstop', f'{self.eventname}.stop')

class JobModel:
    """
    the model for launching computations
    """
    def __init__(self, mdl: Optional['JobModel'] = None):
        self.config:  JobConfig  = JobConfig()  if mdl is None else mdl.config
        self.display: JobDisplay = JobDisplay() if mdl is None else mdl.display

    def swapmodels(self, ctrl):
        "swap models for those in the controller"
        self.config  = ctrl.theme.swapmodels(self.config)
        self.display = ctrl.display.swapmodels(self.display)

    def launch(
            self,
            processors: List[TaskCacheList],
            emitter:    Optional[JobEventNames] = None,
            **kwa
    ):
        """
        Runs jobs synchronously or asynchronously depending on configuration

        Parameters
        ----------

        processors:
            a list of TaskCacheList to run
        emitter:
            in charge of launching start & end events
        """
        return _JobRunner(self).dolaunch(
            processors,
            _JobEventEmitter(emitter, processors = processors, **kwa)
        )

class _JobCanceled(StopIteration):
    pass

class _JobEventEmitter(JobEventNames):
    """Deals with emitting job-related events"""
    _evt: ContextManager

    def __init__(
            self,
            ctrl = None,
            **args
    ):
        super().__init__(ctrl)
        self.ctrl   = getattr(ctrl, '_ctrl', ctrl)
        self.idval  = None
        self.args   = args

    def __call__(self, idval):
        self.idval = idval
        return self

    def __enter__(self):
        "emits a *job starting* event"
        if self.ctrl:
            LOGS.debug("Starting job %s", self.idval)
            self.ctrl.display.handle(
                self.eventjobstart,
                self.ctrl.emitpolicy.outasdict,
                {'idval': self.idval, **self.args}
            )
            self._evt = self.ctrl.display(self.eventname, args = {})
            return self._evt.__enter__()
        return lambda *_, **__: None

    def __exit__(self, extype, *_, **__):
        if hasattr(self, '_evt'):
            out = self._evt.__exit__()
            del self._evt
            if extype is _JobCanceled:
                LOGS.debug("Cancelled job %s", self.idval)

            if extype is not _JobCanceled:
                LOGS.debug("Done job %s", self.idval)
                self.ctrl.display.handle(
                    self.eventjobstop,
                    self.ctrl.emitpolicy.outasdict,
                    {'idval': self.idval, **self.args}
                )
                return out
            return True
        return None

class _JobRunner(JobModel):
    "Running jobs on all TaskCacheList"
    def dolaunch(
            self,
            processors: List[TaskCacheList],
            emitter:    _JobEventEmitter
    ):
        """
        Runs jobs synchronously or asynchronously depending on configuration

        Parameters
        ----------

        processors:
            a list of TaskCacheList to run
        emitter:
            in charge of launching start & end events
        """
        idval = self.display.calls

        if self.config.multiprocess:

            async def _run():
                if idval != self.display.calls:
                    return

                with emitter(idval) as emitup:
                    if self.config.ncpu > 1:
                        await self.run(processors,  emitup, idval)
                    else:
                        self.syncrun(processors)

                    if idval != self.display.calls:
                        raise _JobCanceled()

                    if self.config.ncpu > 1:
                        await asyncio.sleep(self.config.stoptime)

            asyncio.create_task(_run())
            return

        LOGS.info("Starting SYNCH jobs")
        with emitter(idval):
            self.syncrun(processors)
            if idval != self.display.calls:
                raise _JobCanceled()
        LOGS.info("SYNCH jobs done")

    def syncrun(self, processors: List[TaskCacheList]):
        """
        runs all processors sequentially

        Parameters
        ----------

        processors:
            a list of TaskCacheList to run
        emitter:
            in charge of launching start & end events
        """
        for procs in processors:
            frame = next(iter(procs.run()), None)
            if frame is None:
                continue

            if callable(getattr(frame, 'bead', None)):
                raise NotImplementedError()

            store: STORE = procs.data.getcache(DataFrameTask)()

            for keys in self.__split(lambda*_: None, procs):
                if self.config.ncpu <= 0:
                    continue

                for i in keys:
                    try:
                        store[i] = frame[i]
                    except (TrackIOError, ProcessorException) as exc:
                        store[i] = exc

    async def run(
            self,
            processors: List[TaskCacheList],
            events:     Callable[[Dict[str, Any]], None],
            idval:      Optional[int] = None
    ):
        """
        run jobs on provided processors

        Parameters
        ----------

        processors:
            a list of TaskCacheList to run
        events:
            a method emitting an event every time it is called
        """
        # freeze current config
        idcall = self.display.calls if idval is None else idval

        ncpu:  int        = self.config.ncpu
        nprocs: List[int] = [ncpu]

        def _evtfcn(procs: TaskCacheList, beads: List[int]):
            LOGS.debug("-> Processed track %d, beads %s", processors.index(procs), beads)
            try:
                events(dict(idval = idcall, taskcache = procs, beads = beads))
            except Exception as exc:  # pylint: disable=broad-except
                LOGS.exception(exc)

        # create a list allows sending events for all beads already treated
        jobs: List[Tuple[TaskCacheList, Set[int]]] = [
            (procs, keys)
            for procs in processors
            for keys in self.__split(_evtfcn, procs)
        ]

        async def _watchjob(procs: TaskCacheList, keys: Set[int]):
            LOGS.debug("Processing track %d, beads %s", processors.index(procs), keys)
            try:
                async for beads in self.__startjob(procs, keys, idcall):
                    _evtfcn(procs, beads)
            finally:
                nprocs[0] += 1

        if ncpu <= 0:
            return

        # now iterate throught remaining keys
        LOGS.info("%d jobs running in %d separate processes", len(jobs), ncpu)
        for procs, keys in jobs:
            while self.__keepgoing(idcall, nprocs[0] > 0):
                await asyncio.sleep(self.config.waittime)

            if not self.__keepgoing(idcall):
                return

            nprocs[0] -= 1
            asyncio.create_task(_watchjob(procs, keys))

        while self.__keepgoing(idcall, nprocs[0] == ncpu):
            await asyncio.sleep(self.config.waittime)

    @staticmethod
    def _runjob(pipe: Connection, procs: TaskCacheList, keys: List[int]):
        "runs a job"
        if pipe.poll():
            return

        frame = next(iter(procs.run()), None)
        if frame is None:
            pipe.send((None, None))
            return

        if callable(getattr(frame, 'bead', None)):
            raise NotImplementedError()

        for i in keys:
            if pipe.poll():
                return

            try:
                out = (i, frame[i])
            except ProcessorException as exc:
                out = (i, exc)

            if pipe.poll():
                return

            pipe.send(out)

        if not pipe.poll():
            pipe.send((None, None))

    async def __startjob(
            self,
            procs: TaskCacheList,
            keys:  Set[int],
            idval: int
    ) -> AsyncIterator[List[int]]:
        "run a single job"
        cache: Callable[[], STORE] = procs.data.getcache(DataFrameTask)
        store: STORE               = cache()
        if store is None:
            return

        def _keepgoing(done) -> bool:
            return self.__keepgoing(idval, done) and cache() is not None

        pipein, pipeout = Pipe()
        Process(
            target = self._runjob,
            args   = (pipeout, procs.cleancopy(), keys)
        ).start()

        done = False
        while _keepgoing(done):
            await asyncio.sleep(self.config.waittime)

            found: List[int] = []
            while _keepgoing(done or not pipein.poll()):
                ibead, data = pipein.recv()
                done        = ibead is None
                if _keepgoing(done):
                    store[ibead] = data
                    found.append(ibead)

            if _keepgoing(False) and found:
                yield found

        if not done:
            pipein.send(False)

    def __keepgoing(self, idval, done = False) -> bool:
        return not done and idval == self.display.calls

    def __split(
            self,
            events: Callable[[TaskCacheList, List[int]], None],
            procs:  TaskCacheList
    ) -> Iterator[Set[int]]:
        cache = procs.data.getcache(DataFrameTask)()

        try:
            keys = set(next(iter(procs.run()), {}).keys())
        except TrackIOError:
            keys = set(cache if cache else ())

        if cache:
            LOGS.debug("%s has %d processed keys", procs.model[0].path, len(keys - set(cache)))

            keys -= set(cache)
            events(procs, list(cache))

        if keys:
            lkeys = sorted(keys)
            njobs = max(1, len(lkeys) // self.config.maxkeysperjob)

            if (len(lkeys) % self.config.maxkeysperjob) > njobs:
                njobs += 1

            batch = len(lkeys) // njobs
            rem   = len(lkeys) % batch

            LOGS.debug("%s requires %d jobs", procs.model[0].path, len(lkeys)//batch+1)

            for i in range(0, len(lkeys), batch):
                ix1 = i + min(rem, i)
                ix2 = min(ix1 + batch + (i < rem), len(lkeys))
                if ix1 < ix2:
                    yield set(lkeys[ix1:ix2])
