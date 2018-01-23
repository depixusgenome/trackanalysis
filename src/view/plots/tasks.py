#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for dealing with the JS side of the view"
from typing                 import TypeVar
from control.modelaccess    import TaskPlotModelAccess, TaskAccess
from .base                  import PlotCreator

TModelType = TypeVar('TModelType', bound = TaskPlotModelAccess)
class TaskPlotCreator(PlotCreator[TModelType]):
    "Base plotter for tracks"
    def __init__(self, ctrl, *_) -> None:
        super().__init__(ctrl)
        css = self._ctrl.globals.css.plot.title
        if css.stretch.get(default = None) is None:
            self._ctrl.globals.project.bead.default = None
            css.defaults = {'stretch': u'Stretch (base/µm)', 'bias': u'Bias (µm)'}

    def observe(self):
        "sets-up model observers"
        super().observe()

        if any(isinstance(i, TaskAccess) for i in self._model.__dict__.values()):
            def _ontask(parent = None, task = None, **_):
                if self._model.impacts(parent, task):
                    self.reset(False)
            self._ctrl.observe("updatetask", "addtask", "removetask", _ontask)

    def _create(self, doc):
        raise NotImplementedError()

    def _reset(self):
        raise NotImplementedError()
