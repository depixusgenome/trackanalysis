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
    def __init__(self, *args):
        super().__init__(*args)
        self._widgets = QualityControlWidgets(self._model)
        self._plots   = QualityControlPlots  (self._ctrl, self._model)

    def observe(self):
        "observes the model"
        super().observe()
        self._widgets.observe()
        self._plots  .observe()

    def _create(self, doc):
        "returns the figure"
        mode    = self.defaultsizingmode()
        widgets = self._widgets.create(self.action, mode)
        grid    = self._plots.create(doc, mode)
        return layouts.row(grid, widgets)

    def _reset(self):
        self._widgets.reset(self._bkmodels)
        self._plots.reset(self._bkmodels)

class QualityControlView(PlotView[QualityControlPlotCreator]):
    "a widget with all discards messages"
    TASKS       = 'datacleaning', 'extremumalignment'
    PANEL_NAME  = 'Quality Control'
    def ismain(self):
        "Cleaning and alignment, ... are set-up by default"
        super()._ismain(tasks = self.TASKS)
