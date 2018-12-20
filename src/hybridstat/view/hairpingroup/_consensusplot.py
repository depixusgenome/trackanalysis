#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows consensus bead"
import numpy as np
from bokeh            import layouts
from bokeh.plotting   import Figure
from bokeh.models     import Range1d, ColumnDataSource

from view.colors      import tohex
from view.plots.base  import themed, PlotView, CACHE_TYPE, GroupStateDescriptor
from view.plots.tasks import TaskPlotCreator
from .._io            import setupio
from ..cyclehistplot  import BaseHistPlotCreator
from ._model          import (ConsensusModelAccess, ConsensusScatterModel,
                              ConsensusScatterTheme, ConsensusHistPlotModel)
from ._plot           import setpoolobservers
from ._widget         import ConsensusPlotWidgets

class ConsensusHistPlotCreator(
        BaseHistPlotCreator[ConsensusModelAccess, ConsensusHistPlotModel]
):
    "Creates hist for a consensus bead"
    _model: ConsensusModelAccess
    def _createpeaks(self, dtls, data):
        peaks, allpks, factor = self._model.consensuspeaks(dtls)
        colors = [tohex(themed(self._model.themename, self._theme.pkcolors)[i])
                  for i in ('found', 'missing')]
        if dtls is not None:
            dtls.histogram /= factor
        peaks['color']    = np.where(np.isfinite(peaks['id']), *colors[:2])
        allpks['color']   = np.where(np.isfinite(allpks['id']), *colors[:2])
        data['peaks']     = peaks
        data['beadpeaks'] = allpks
        return True

    def create(self, ctrl, doc, *_):
        "create the figure"
        return self._addtodoc(ctrl, doc, *_)

    @property
    def beadpeaks(self):
        "return bead peaks"
        return self._src['beadpeaks']

    @property
    def peaks(self):
        "return peaks"
        return self._src['peaks']

    @staticmethod
    def _tobases(arr):
        return arr

class ConsensusScatterPlotCreator(
        TaskPlotCreator[ConsensusModelAccess, ConsensusScatterModel]
):
    "Creates scatter plot of rates & durations"
    _model:  ConsensusModelAccess
    _theme:  ConsensusScatterTheme
    _src:    ColumnDataSource
    _fig:    Figure
    def _addtodoc(self, ctrl, doc, *_): # pylint: disable=unused-argument,no-self-use
        assert False

    def create(self, source):
        "create the plot"
        self._src  = source
        self._fig  = self.figure(y_range = Range1d, x_range = Range1d)
        self.addtofig(self._fig, 'peaks', x = 'count', y = 'duration', source = self._src)
        self.linkmodeltoaxes(self._fig)
        return self._fig

    def _reset(self, cache: CACHE_TYPE):
        if self._src in cache and 'data' in cache[self._src]:
            data = cache[self._src]['data']
        else:
            data = self._src.data
        self.setbounds(cache, self._fig, data['count'], data["duration"])

@GroupStateDescriptor(*(f"consensus.plot.{i}" for i in ("hist", "scatter")))
class ConsensusPlotCreator(TaskPlotCreator[ConsensusModelAccess, None]):
    "Building scatter & hist plots"
    def __init__(self, ctrl):
        super().__init__(ctrl, addto = False)
        args = {'noerase': False, 'model':   self._model}
        self._scatter  = ConsensusScatterPlotCreator(ctrl, **args)
        self._hist     = ConsensusHistPlotCreator(ctrl, **args)
        self._widgets  = ConsensusPlotWidgets(ctrl, self._model)
        self.addto(ctrl)

    @property
    def plots(self):
        "return figure list"
        return [self._hist, self._scatter]

    def observe(self, ctrl):
        "observes the model"
        super().observe(ctrl)
        self._widgets.observe(ctrl)
        setpoolobservers(self, ctrl, self._model, "consensus.plot.scatter")

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        self._scatter.addto(ctrl, noerase=noerase)
        self._hist.addto(ctrl, noerase=noerase)

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        hist    = self._hist.create(ctrl, doc)
        scatter = self._scatter.create(self._hist.beadpeaks)
        mode    = self.defaultsizingmode()
        widg    = self._widgets.addtodoc(self, ctrl, doc, self._hist.peaks)
        return layouts.row(layouts.column(scatter, widg, **mode), hist, **mode)

    def advanced(self):
        "triggers the advanced dialog"
        self._widgets.advanced.on_click()

    def ismain(self, _):
        "specific setup for when this view is the main one"
        self._widgets.advanced.ismain(_)

    def _statehash(self):
        return self._model.statehash(task = ...)

    def _reset(self, cache:CACHE_TYPE):
        done = 0
        try:
            self._hist.delegatereset(cache)
            done += 1
        finally:
            try:
                self._scatter.delegatereset(cache)
                done += 1
            finally:
                try:
                    self._widgets.reset(cache, done != 2)
                finally:
                    pass

@setupio
class ConsensusPlotView(PlotView[ConsensusPlotCreator]):
    "Peaks plot view"
