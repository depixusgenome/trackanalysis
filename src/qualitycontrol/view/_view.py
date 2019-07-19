#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing               import cast
from    bokeh                import layouts
from    model.plots          import PlotState
from    taskview.plots       import PlotView, CACHE_TYPE, TaskPlotCreator
from    utils                import initdefaults
from    ._widgets            import QualityControlWidgets
from    ._plots              import QualityControlPlots
from    ._model              import QualityControlModelAccess

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
    _plotmodel: None
    _model:     QualityControlModelAccess
    _RESET:     frozenset = frozenset()
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
        out     = layouts.row(grid, widgets, **mode)
        self.__resize(ctrl, out)
        return out

    def _reset(self, cache:CACHE_TYPE):
        self._widgets.reset(cache)
        self._plots.reset(cache)

    def __resize(self, ctrl, sizer):
        figtb   = ctrl.theme.get("theme", "figtbheight")
        borders = ctrl.theme.get("theme", "borders")

        sizer.update(**self.defaulttabsize(ctrl))

        widg  = sizer.children[1]
        width = max(i.width for i in widg.children)
        for i in widg.children:
            i.width = width
        widg.children[-1].height = (
            sizer.height - sum(i.height for i in widg.children[:-1])-figtb
        )
        widg.update(width  = width, height = sizer.height)

        sizer.children[0].update(width = sizer.width-width, height = sizer.height)
        sizer.children[0].children[1].update(
            width  = sizer.width-width-borders,
            height = sizer.height
        )
        plots = sizer.children[0].children[1].children[1].children
        for i in plots:
            i[0].update(
                plot_width  = sizer.children[0].children[1].width,
                plot_height = (sizer.height-figtb)//len(plots)
            )

class QualityControlView(PlotView[QualityControlPlotCreator]):
    "a widget with all discards messages"
    TASKS       = 'datacleaning', 'extremumalignment'
    PANEL_NAME  = 'Quality Control'
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks = self.TASKS)
