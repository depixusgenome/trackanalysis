#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from typing                 import TypeVar
from abc                    import abstractmethod
from control.modelaccess    import TaskPlotModelAccess, TaskAccess
from .base                  import PlotCreator

TModelType = TypeVar('TModelType', bound = TaskPlotModelAccess)
class TaskPlotCreator(PlotCreator[TModelType]):
    "Base plotter for tracks"
    def __init__(self, ctrl, *_) -> None:
        super().__init__(ctrl)
        css = ctrl.globals.css.plot.title
        if css.stretch.get(default = None) is None:
            css.defaults = {'stretch': u'Stretch (base/µm)', 'bias': u'Bias (µm)'}

    def _onchangetask(self, parent = None, task = None, **_):
        if self._model.impacts(parent, task):
            self.reset(False)

    def _onchangedisplay(self, old = None, **_):
        self.reset('roottask' in old)

    def observe(self, ctrl):
        "sets-up model observers"
        self._model.settaskmodel(ctrl, "tasks")
        ctrl.display.observe("tasks", self._onchangedisplay)
        if any(isinstance(i, TaskAccess) for i in self._model.__dict__.values()):
            ctrl.tasks.observe("updatetask", "addtask", "removetask", self. _onchangetask)

    @abstractmethod
    def _addtodoc(self, ctrl, doc):
        pass

    @abstractmethod
    def _reset(self):
        pass
