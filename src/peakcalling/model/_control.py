#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating list of jobs to run"
import asyncio
from typing      import Iterator, TYPE_CHECKING, cast

from taskmodel       import RootTask
from utils.logconfig import getLogger
from ._jobs          import JobModel, JobEventNames
from ._tasks         import TasksModel, Processors
from ._diskcache     import DiskCacheController, DiskCache

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from taskapp.maincontrol  import SuperController  # noqa


LOGS = getLogger(__name__)


class TasksModelController(JobEventNames):
    """
    Centralises information needed for processing & displaying
    multiple fields of view.

    Parameters
    ----------
    _jobs:
        an object tasked with running computations on all FoVs
    _tasks:
        holds the information such as task lists, ..., on all FoVs
    """
    _ctrl: 'SuperController'
    jobs:      JobModel   = cast(JobModel,   property(lambda self: getattr(self, '_jobs')))
    tasks:     TasksModel = cast(TasksModel, property(lambda self: getattr(self, '_tasks')))
    diskcache: DiskCache  = cast(DiskCache,  property(lambda self: getattr(self, '_disk').config))

    def __init__(self):
        super().__init__()
        self._jobs:  JobModel            = JobModel()
        self._tasks: TasksModel          = TasksModel()
        self._disk:  DiskCacheController = DiskCacheController(self._jobs)

    @property
    def roots(self) -> Iterator[RootTask]:
        "ordered iteration over roots"
        return self.tasks.roots

    def swapmodels(self, ctrl):
        "swap models with those in the controller"
        for i in self.__dict__.values():
            if callable(getattr(i, 'swapmodels', None)):
                i.swapmodels(ctrl)

    def observe(self, ctrl):
        "add reactions to updates occurring throught the controller"
        self._ctrl = ctrl
        for i in self.__dict__.values():
            if callable(getattr(i, 'observe', None)):
                i.observe(ctrl)

        @ctrl.display.observe(self._tasks.tasks.name)
        @ctrl.display.hashwith(self._jobs.display)
        def _ontasks(**_):
            self._relaunch(ctrl)

        @ctrl.display.observe(self._jobs.display)
        @ctrl.display.hashwith(self._jobs.display)
        def _onchange(old, _evts_ = frozenset(('calls', 'active')), **_):
            if not _evts_.intersection(old):
                return

            if not self._jobs.display.needsrefresh:
                LOGS.debug("no refresh needed")
                return

            async def _launch(_id_ = self._jobs.display.calls):
                if _id_ != self._jobs.display.calls:
                    return

                LOGS.debug("launching")
                self._jobs.launch(
                    list(self._tasks.processors.values()),
                    self,
                    roots   = list(self.roots),
                    missing = self._tasks.missingprocessors
                )

            LOGS.debug("refresh needed")
            # launch after the current task is done: this makes sure
            # all updates are done
            asyncio.create_task(_launch())

        @ctrl.display.observe(self.eventjobstart)
        @ctrl.display.hashwith(self._jobs.display)
        def _onjobstart(idval, **_):
            if idval is not None:
                ctrl.display.update(
                    self._jobs.display, last = max(self._jobs.display.last, idval)
                )

    def addto(self, ctrl):
        "add to the controller"
        if getattr(self, '_ctrl', None) is not ctrl:
            assert not hasattr(self, '_ctrl')  # controller change not implemented
            self.swapmodels(ctrl)
            self.observe(ctrl)

    def updatediskcache(self, ctrl, reset = False, processors = None, ncpu = None, **kwa):
        "update the disk cache config"
        if ncpu is not None:
            ctrl.theme.update(self.jobs.config, ncpu = ncpu)

        old = self.diskcache.maxsize
        if kwa:
            ctrl.theme.update(self.diskcache, **kwa)

        if processors is None:
            processors = []

        if reset:
            procs = list(self.processors.values())
            processors.extend(procs)

            for i in procs:
                self._tasks.tasks.clear(i)

        if processors and self.diskcache.maxsize > 0:
            self.diskcache.clear(processors = processors)

        if reset or (kwa.get('maxsize', 0) > 0 and old == 0):
            self._relaunch(ctrl)

    @property
    def processors(self) -> Processors:
        """return the processors for new jobs"""
        return self._tasks.processors

    def _relaunch(self, ctrl, ):
        disp = self._jobs.display
        ctrl.display.update(disp, calls = disp.calls+1)
