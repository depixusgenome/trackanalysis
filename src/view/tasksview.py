#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from model.task.application import TasksModel

class TasksView:
    "View listing all tasks global info"
    def __init__(self, **kwa):
        self._model   = TasksModel(**kwa)

    def observe(self, ctrl):
        "observing the controller"
        if self._model.theme.name in ctrl.theme:
            self._model.theme   = ctrl.theme.model(self._model.theme.name)
            self._model.display = ctrl.display.model(self._model.display.name)

        else:
            ctrl.theme.add(self._model.theme)
            ctrl.display.add(self._model.display)

        @ctrl.tasks.observe
        def _onclosetrack(**_):
            inst = next(ctrl.tasks.tasklist(...), None)
            if inst is not None:
                inst = next(iter(inst), None)
            ctrl.display.update(self._model.display, roottask = inst)

        @ctrl.tasks.observe
        def _onopentrack(model = None, **_):
            ctrl.display.update(self._model.display, roottask = model[0], bead = None)
