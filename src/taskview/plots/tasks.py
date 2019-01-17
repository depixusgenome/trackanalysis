#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from typing                  import TypeVar
from abc                     import abstractmethod
from taskcontrol.modelaccess import TaskPlotModelAccess, TaskAccess
from .base                   import PlotCreator, PlotModelType, CACHE_TYPE

TModelType = TypeVar('TModelType', bound = TaskPlotModelAccess)
class TaskPlotCreator(PlotCreator[TModelType, PlotModelType]):
    "Base plotter for tracks"
    def _onchangetask(self, parent = None, task = None, calllater = None, **_):
        if self._model.impacts(parent, task):
            calllater.append(lambda: self.reset(False))

    def _onchangedisplay(self, old = None, calllater = None, **_):
        calllater.append(lambda: self.reset('roottask' in old))

    def observetasks(self, ctrl, name = "tasks"):
        "sets-up task model observers"
        ctrl.display.observe(name, self._onchangedisplay)
        if any(isinstance(i, TaskAccess) for i in self._model.__dict__.values()):
            ctrl.tasks.observe("updatetask", "addtask", "removetask", self. _onchangetask)

    def observe(self, ctrl, noerase = True):
        "sets-up model observers"
        super().observe(ctrl, noerase)
        self.observetasks(ctrl)

    @abstractmethod
    def _addtodoc(self, ctrl, doc, *_):
        pass

    @abstractmethod
    def _reset(self, cache:CACHE_TYPE):
        pass
