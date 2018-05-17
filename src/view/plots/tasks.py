#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from typing                 import TypeVar
from abc                    import abstractmethod
from control.modelaccess    import TaskPlotModelAccess, TaskAccess
from .base                  import PlotCreator, PlotModelType, CACHE_TYPE

TModelType = TypeVar('TModelType', bound = TaskPlotModelAccess)
class TaskPlotCreator(PlotCreator[TModelType, PlotModelType]):
    "Base plotter for tracks"
    def _onchangetask(self, parent = None, task = None, **_):
        if self._model.impacts(parent, task):
            self.reset(False)

    def _onchangedisplay(self, old = None, **_):
        self.reset('roottask' in old)

    def observe(self, ctrl):
        "sets-up model observers"
        super().observe(ctrl)
        self._model.settaskmodel(ctrl, "tasks")
        ctrl.display.observe("tasks", self._onchangedisplay)
        if any(isinstance(i, TaskAccess) for i in self._model.__dict__.values()):
            ctrl.tasks.observe("updatetask", "addtask", "removetask", self. _onchangetask)

    @abstractmethod
    def _addtodoc(self, ctrl, doc):
        pass

    @abstractmethod
    def _reset(self, cache:CACHE_TYPE):
        pass
