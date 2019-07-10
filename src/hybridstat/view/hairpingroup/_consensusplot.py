#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows consensus bead"
import numpy as np
from bokeh            import layouts
from bokeh.plotting   import Figure
from bokeh.models     import Range1d, ColumnDataSource, HoverTool

from taskview.plots   import TaskPlotCreator
from view.colors      import tohex
from view.plots       import PlotView, GroupStateDescriptor, themed, CACHE_TYPE
from .._io            import setupio
from ..cyclehistplot  import BaseHistPlotCreator
from ._model          import (ConsensusModelAccess, ConsensusScatterModel,
                              ConsensusScatterTheme, ConsensusHistPlotModel,
                              ConsensusConfig)
from ._plot           import setpoolobservers
from ._widget         import ConsensusPlotWidgets

class ConsensusHistPlotCreator(
        BaseHistPlotCreator[ConsensusModelAccess, ConsensusHistPlotModel]
):
    "Creates hist for a consensus bead"
    _model: ConsensusModelAccess
    def _createpeaks(self, itms, out):
        peaks, allpks, factor = self._model.consensuspeaks(itms)
        colors = [tohex(themed(self._model.themename, self._theme.pkcolors)[i])
                  for i in ('found', 'missing')]
        if itms is not None:
            itms.histogram /= factor
        peaks['color']  = np.where(np.isfinite(peaks['id']), *colors[:2])
        allpks['color'] = np.where(np.isfinite(allpks['id']), *colors[:2])
        out['peaks']    = peaks
        out['events']   = allpks
        out['events']['rate'] = out['events']['count']
        return True

    def create(self, ctrl, doc, *_):
        "create the figure"
        return self._addtodoc(ctrl, doc, *_)

    @property
    def events(self):
        "return bead peaks"
        return self._src['events']

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
        rend       = self.addtofig(
            self._fig, 'peaks', x = 'rate', y = 'duration', source = self._src
        )
        self.linkmodeltoaxes(self._fig)

        hover = self._fig.select(HoverTool)
        if len(hover) > 0:
            hover = hover[0]
            hover.update(
                point_policy = self._theme.tooltippolicy,
                tooltips     = self._theme.tooltips,
                mode         = self._theme.tooltipmode,
                renderers    = [rend]
            )

        return self._fig

    def _reset(self, cache: CACHE_TYPE):
        if self._src in cache and 'data' in cache[self._src]:
            data = cache[self._src]['data']
        else:
            data = self._src.data
        self.setbounds(cache, self._fig, data['rate'], data["duration"])

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

    def observe(self, ctrl, noerase = True):
        "observes the model"
        super().observe(ctrl, noerase = noerase)
        self._widgets.observe(ctrl)
        setpoolobservers(self, ctrl, self._model, "consensus.plot.scatter")

        @ctrl.theme.observe(ConsensusConfig().name)
        def _on_cnf(**_):
            self.reset(False)

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        self._scatter.addto(ctrl, noerase=noerase)
        self._hist.addto(ctrl, noerase=noerase)

    def _addtodoc(self, ctrl, doc, *_):
        "returns the figure"
        hist    = self._hist.create(ctrl, doc)
        scatter = self._scatter.create(self._hist.events)
        mode    = self.defaultsizingmode()
        widg    = self._widgets.addtodoc(self, ctrl, doc, self._hist.peaks)
        out         = layouts.row(
            layouts.column(hist,  **mode),
            layouts.column(scatter, widg, **mode),
            **mode
        )
        self.__resize(ctrl, out)
        return out

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

    def __resize(self, ctrl, sizer):
        sizer.update(**self.defaulttabsize(ctrl))
        borders = ctrl.theme.get("theme", "borders")

        hist           = sizer.children[0].children[0]
        scatter, widg  = sizer.children[1].children

        scatter.update(
            plot_width  = widg.width,
            plot_height = widg.width
        )
        widg.children[-1].height = (
            sizer.height
            - scatter.plot_height
            - sum(i.height+2*borders for i in widg.children[:-1])
        )
        widg.height = sum(i.height for i in widg.children)
        hist.update(
            plot_width  = sizer.width - scatter.plot_width - borders,
            plot_height = sizer.height
        )
        sizer.children[0].update(
            width  = sizer.width - scatter.plot_width,
            height = sizer.height
        )
        sizer.children[1].update(
            width  = scatter.plot_width,
            height = sizer.height
        )

@setupio
class ConsensusPlotView(PlotView[ConsensusPlotCreator]):
    "Peaks plot view"
