#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from ._plot import CleaningPlotCreator, CleaningView, PlotView, CleaningPlotModel

class BeadCleaningPlotCreator(CleaningPlotCreator):
    "Building the graph of cycles"
    def __init__(self, ctrl, **kwa):
        plotmodel = CleaningPlotModel()
        plotmodel.theme.name         = "cleaning.bead"
        plotmodel.display.name       = "cleaning.bead"
        plotmodel.theme.name         = "cleaning.bead"
        plotmodel.theme.lines.alpha  = 1.
        plotmodel.theme.points.alpha = 1.
        super().__init__(ctrl, plotmodel = plotmodel, **kwa)

    def _data(self, items, nans):
        data   = super()._data(items, nans)
        if len(data['t']) > 1:
            data['t'] += self._model.track.phases[:, 0][data['cycle']]
        return data

class BeadCleaningView(PlotView[BeadCleaningPlotCreator]):
    "Peaks plot view"
    TASKS = CleaningView.TASKS

    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks  = self.TASKS)
