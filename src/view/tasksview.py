#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from functools              import partial
from model.task.application import TasksModel

class TasksView:
    "View listing all tasks global info"
    def __init__(self, **kwa):
        self._model = TasksModel(**kwa)

    def _onclosetrack(self, ctrl, **_):
        inst = next(ctrl.tasks.tasklist(...), None)
        if inst is not None:
            inst = next(iter(inst), None)
        ctrl.display.update(self._model.display, roottask = inst)

    def _onopentrack(self, ctrl, model = None, **_):
        ctrl.display.update(self._model.display, roottask = model[0], bead = None)

    def observe(self, ctrl):
        "observing the controller"
        self._model.addtocontroller(ctrl, False)
        ctrl.tasks.observe(closetrack = partial(self._onclosetrack, ctrl),
                           opentrack  = partial(self._onopentrack,  ctrl))
