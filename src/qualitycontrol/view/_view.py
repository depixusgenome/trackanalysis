#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    bokeh             import layouts
from    view.plots        import PlotView
from    view.plots.tasks  import TaskPlotCreator
from    ._widgets         import QualityControlWidgets
from    ._plots           import QualityControlPlots
from    ._model           import QualityControlModelAccess

class QualityControlPlotCreator(TaskPlotCreator[QualityControlModelAccess]):
    "Creates plots for discard list"
    _RESET = frozenset()         # type: frozenset
    def __init__(self, ctrl = None, *args): # pylint: disable=keyword-arg-before-vararg
        super().__init__(ctrl = ctrl, *args)
        self._widgets = QualityControlWidgets(self._model)
        self._plots   = QualityControlPlots  (ctrl, self._model)

    def observe(self, ctrl):
        "observes the model"
        self._model.settosame(ctrl)
        super().observe(ctrl)
        self._widgets.observe(ctrl)
        self._plots  .observe(ctrl)

    def _addtodoc(self, _, doc):
        "returns the figure"
        mode    = self.defaultsizingmode()
        widgets = self._widgets.addtodoc(self.action, mode)
        grid    = self._plots.addtodoc(doc, mode)
        return layouts.row(grid, widgets)

    def _reset(self):
        self._widgets.reset(self._bkmodels)
        self._plots.reset(self._bkmodels)

class QualityControlView(PlotView[QualityControlPlotCreator]):
    "a widget with all discards messages"
    TASKS       = 'datacleaning', 'extremumalignment'
    PANEL_NAME  = 'Quality Control'
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks = self.TASKS)
