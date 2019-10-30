#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating list of jobs to run"
from typing                     import TYPE_CHECKING, cast

from ._jobs                     import JobModel, JobEventNames
from ._tasks                    import TasksModel, Processors

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from taskapp.maincontrol  import SuperController  # noqa

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
    jobs:  JobModel   = cast(JobModel,   property(lambda self: getattr(self, '_jobs')))
    tasks: TasksModel = cast(TasksModel, property(lambda self: getattr(self, '_tasks')))

    def __init__(self):
        super().__init__()
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

        calls = [self._jobs.display.calls]

        @ctrl.display.observe(self._tasks.tasks.name)
        @ctrl.display.hashwith(self._jobs.display)
        def _ontasks(**_):
            calls[0] += 1
            ctrl.display.update(self._jobs.display, calls = calls[0])

        @ctrl.display.observe(self._jobs.display)
        @ctrl.display.hashwith(self._jobs.display)
        def _onchange(**_):
            self._jobs.launch(list(self._tasks.processors.values()), self)

    def addto(self, ctrl):
        "add to the controller"
        if getattr(self, '_ctrl', None) is not ctrl:
            assert not hasattr(self, '_ctrl')  # controller change not implemented
            self.swapmodels(ctrl)
            self.observe(ctrl)

    @property
    def processors(self) -> Processors:
        """return the processors for new jobs"""
        return self._tasks.processors
