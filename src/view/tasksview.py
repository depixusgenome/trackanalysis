#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from functools              import partial
from model.task             import Task
from model.task.application import TasksModel, TaskIOTheme

class TasksView:
    "View listing all tasks global info"
    def __init__(self, ctrl):
        self._model = TasksModel()
        self._model.addto(ctrl, False)
        ctrl.theme.add(TaskIOTheme(), False)

    def _onclosetrack(self, ctrl, **_):
        inst = next(ctrl.tasks.tasklist(...), None)
        if inst is not None:
            inst = next(iter(inst), None)
        ctrl.display.update(self._model.display, roottask = inst)

    def _onopentrack(self, ctrl, model = None, calllater = None, **_):
        calllater.insert(0, partial(self._openedtrack, ctrl,  model[0]))

    def _openedtrack(self, ctrl, root: Task):
        ctrl.display.update(self._model.display, roottask = root, bead = None)

    def observe(self, ctrl):
        "observing the controller"
        self._model.addto(ctrl, False)
        ctrl.theme.add(TaskIOTheme(), False)
        ctrl.tasks.observe(closetrack = partial(self._onclosetrack, ctrl),
                           opentrack  = partial(self._onopentrack,  ctrl))
