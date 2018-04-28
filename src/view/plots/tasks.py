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

    def observe(self, ctrl):
        "sets-up model observers"
        super().observe(ctrl)

        if any(isinstance(i, TaskAccess) for i in self._model.__dict__.values()):
            def _ontask(parent = None, task = None, **_):
                if self._model.impacts(parent, task):
                    self.reset(False)
            ctrl.observe("updatetask", "addtask", "removetask", _ontask)

    @abstractmethod
    def _addtodoc(self, ctrl, doc):
        pass

    @abstractmethod
    def _reset(self):
        pass
