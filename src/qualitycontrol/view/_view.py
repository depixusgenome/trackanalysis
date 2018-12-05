#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing            import cast
from    bokeh             import layouts
from    model.plots       import PlotState
from    utils             import initdefaults
from    view.plots        import PlotView, CACHE_TYPE
from    view.plots.tasks  import TaskPlotCreator
from    ._widgets         import QualityControlWidgets
from    ._plots           import QualityControlPlots
from    ._model           import QualityControlModelAccess

class _StateDescriptor:
    def __get__(self, inst, owner):
        return getattr(inst, '_state').state if inst else self

    @staticmethod
    def setdefault(inst, value):
        "sets the default value"
        getattr(inst, '_ctrl').display.updatedefaults("qc.state", state = PlotState(value))

    def __set__(self, inst, value):
        getattr(inst, '_ctrl').display.update("qc.state", state = PlotState(value))

class QCPlotState:
    "qc plot state"
    state = PlotState.active
    name  = "qc.state"
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class QualityControlPlotCreator(TaskPlotCreator[QualityControlModelAccess, None]):
    "Creates plots for discard list"
    _RESET: frozenset = frozenset()
    state = cast(PlotState, _StateDescriptor())
    def __init__(self, ctrl):
        super().__init__(ctrl, addto = False)
        self._widgets = QualityControlWidgets(ctrl, self._model)
        self._plots   = QualityControlPlots  (ctrl, self._model)
        self._state   = QCPlotState()
        ctrl.display.add(self._state)

    def observe(self, ctrl, noerase = True):
        "observes the model"
        super().observe(ctrl, noerase = noerase)
        self._plots  .observe(ctrl)
        self._widgets.observe(self, ctrl)

    def _addtodoc(self, ctrl, doc, *_):
        "returns the figure"
        mode    = self.defaultsizingmode()
        widgets = self._widgets.addtodoc(self, ctrl, mode)
        grid    = self._plots.addtodoc(self._ctrl, doc, mode)
        return layouts.row(grid, widgets)

    def _reset(self, cache:CACHE_TYPE):
        self._widgets.reset(cache)
        self._plots.reset(cache)

class QualityControlView(PlotView[QualityControlPlotCreator]):
    "a widget with all discards messages"
    TASKS       = 'datacleaning', 'extremumalignment'
    PANEL_NAME  = 'Quality Control'
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks = self.TASKS)
