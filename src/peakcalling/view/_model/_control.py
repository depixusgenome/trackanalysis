#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating list of jobs to run"
from typing                     import Dict, TYPE_CHECKING

import asyncio

from taskcontrol.taskcontrol    import ProcessorController
from taskmodel                  import RootTask
from ._jobs                     import JobModel, JobRunner
from ._tasks                    import TasksModel

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from taskapp.maincontrol  import SuperController  # noqa

class TasksModelController:
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

    def __init__(self):
        self._jobs:  JobModel   = JobModel()
        self._tasks: TasksModel = TasksModel()

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

        @ctrl.display.observe(self._tasks.state)
        @ctrl.display.hashwith(self._tasks.state)
        def _onclosetrack(**_):
            ctrl.display.update(self._jobs.display, calls = self._jobs.display.calls+1)

        @ctrl.display.observe(self._jobs.display)
        @ctrl.display.hashwith(self._tasks.state)
        def _onchange(**_):
            idval = self._jobs.display.calls
            procs = list(self._tasks.processors().values())

            async def _run():
                with ctrl.display("peakcalling.view", args = {}) as sendevt:
                    JobRunner(self._jobs).run(procs, sendevt, idval)

            asyncio.create_task(_run())

    def addto(self, ctrl):
        "add to the controller"
        if getattr(self, '_ctrl', None) is not ctrl:
            assert not hasattr(self, '_ctrl')  # controller change not implemented
            self.swapmodels(ctrl)
            self.observe(ctrl)

    @property
    def processors(self) -> Dict[RootTask, ProcessorController]:
        """return the processors for new jobs"""
        return self._tasks.processors
