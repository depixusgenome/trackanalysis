#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View for seeing all beads together peaks"
from typing                 import Dict, List
import numpy as np

from bokeh.plotting         import Figure
from bokeh.models           import (ColumnDataSource, Range1d, FactorRange,
                                    NumeralTickFormatter, HoverTool, LinearAxis)
from bokeh.transform        import jitter
from view.plots             import PlotView
from view.plots.ploterror   import PlotError
from view.plots.tasks       import TaskPlotCreator, CACHE_TYPE
from .._model               import resetrefaxis
from .._io                  import setupio
from ._model                import (GroupedBeadsPlotModel, GroupedBeadsModelAccess,
                                    GroupedBeadsPlotTheme, GroupedBeadsHistModel,
                                    GroupedBeadsHistTheme)

ColumnData = Dict[str, np.ndarray]
FigData    = Dict[str, ColumnData]
class GroupedBeadsPlotCreator(TaskPlotCreator[GroupedBeadsModelAccess, GroupedBeadsPlotModel]):
    "Building a scatter plot of beads vs hybridization positions"
    _model:  GroupedBeadsModelAccess
    _theme:  GroupedBeadsPlotTheme
    _src:    Dict[str, ColumnDataSource]
    _fig:    Figure
    _ref:    LinearAxis
    _errors: PlotError
    def _addtodoc(self, ctrl, *_):
        self._src = {i: ColumnDataSource(data = j) for i, j in self._data(None).items()}
        self._fig = self.figure(y_range = Range1d, x_range = FactorRange())
        self._ref = LinearAxis(axis_label = self._theme.reflabel,
                               formatter  = NumeralTickFormatter(format = "0"))
        self._fig.add_layout(self._ref, 'right')

        jtr       = jitter("bead", range = self._fig.x_range, width = .75)
        self.addtofig(self._fig, "events", x = jtr,    y = 'bases',
                      source = self._src["events"])
        rend = self.addtofig(self._fig, "peaks",  x = "bead", y = 'bases',
                             source = self._src["peaks"])
        hover = self._fig.select(HoverTool)
        if len(hover) > 0:
            hover = hover[0]
            hover.update(point_policy = self._theme.tooltippolicy,
                         tooltips     = self._theme.tooltips,
                         mode         = self._theme.tooltipmode,
                         renderers    = [rend])

        self._display.addcallbacks(ctrl, self._fig)
        self._fig.yaxis.formatter = NumeralTickFormatter(format = self._theme.format)
        self._errors = PlotError(self._fig, self._theme)
        return self._fig

    def _reset(self, cache: CACHE_TYPE):
        def _data():
            return self._model.runbead()

        def _display(items):
            data  = self._data(items)
            beads = [str(i) for i in sorted(set(data['events']['bead']))]
            cache[self._fig.x_range].update(factors = beads,
                                            start   = -.5,
                                            end     = len(beads)-.5,
                                            bounds  = [-.5, len(beads)-.5])
            self.setbounds(cache, self._fig.y_range, 'y', data['events']['bases'])
            cache[self._ref] = resetrefaxis(self._model, self._theme.reflabel)
            for i, j in data.items():
                cache[self._src[i]]['data'] = j

        self._errors(cache, _data, _display)

    @staticmethod
    def _data(items) -> FigData:
        if items is None:
            items = {}

        def _create(cols, itr):
            info: Dict[str, List[np.ndarray]] = {i: [] for i in cols}
            for i, j in ((i, _[itr]) for i, _ in items.items()):
                if isinstance(j, dict):
                    for k in cols:
                        info[k].append(j[k])
                else:
                    info["bases"].append(j)
                info['bead'].append(np.full(len(info["bases"][-1]), str(i), dtype='<U3'))
            return {i: np.concatenate(i) for i, j in info.items()}

        cols = ('bead', 'bases', 'id', 'orient', 'duration', 'count')
        return {"events": _create(('bead', 'bases'), False),
                "peaks":  _create(cols, True)}

class GroupedHistPlotCreator(TaskPlotCreator[GroupedBeadsModelAccess, GroupedBeadsHistModel]):
    "Building a histogram for a given peak characteristic"
    _model:     GroupedBeadsModelAccess
    _theme:     GroupedBeadsHistTheme
    _src:       ColumnDataSource
    _peaks:     ColumnDataSource
    _fig:       Figure
    def _addtodoc(self, ctrl, *_):
        self._src = ColumnDataSource(data = {'x': [], 'y': []})
        self._fig = self.figure(y_range = Range1d, x_range = FactorRange())
        self.addtofig(self._fig, "hist", x = "x",    y = 'y', source = self._src)
        self._display.addcallbacks(ctrl, self._fig)
        return self._fig

    def _reset(self, cache: CACHE_TYPE):
        cache[self._src]['data'] = data = self._data()
        self.setbounds(cache, self._fig.x_range, 'x', data['x'])
        self.setbounds(cache, self._fig.y_range, 'y', data['y'])

    _empty = np.empty(0, dtype = 'f4')
    def _data(self) -> Dict[str, np.ndarray]:
        items = self._peaks
        if items is None:
            return {i: self._empty for i in 'xy'}

        vals  = items.data[self._theme.xdata]
        if len(vals):
            sel   = getattr(items.selected, "indices", None)
            if sel is not None:
                vals = vals[sel]

        if len(vals) == 0:
            return {i: self._empty for i in 'xy'}

        rng   = np.nanmax(vals), np.nanmin(vals)
        bsize = self._theme.binsize
        edges = np.arange(int((rng[0]-rng[1])/bsize)+1, dtype = 'f4')*bsize+rng[-1]
        return {"x": edges, "y": np.histogram(vals, bins = edges)}

    def onselected_cb(self, attr, old, new):
        "on selected"
        with self.resetting() as cache:
            self._reset(cache)

class GroupedBeadsPlotView(PlotView[GroupedBeadsPlotCreator]):
    "Peaks plot view"
    PANEL_NAME = 'Cycles & Peaks'
    TASKS      = ('extremumalignment', 'clipping', 'eventdetection', 'peakselector',
                  'singlestrand')
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self, ctrl):
        "Alignment, ... is set-up by default"
        self._ismain(ctrl, tasks = self.TASKS,
                     **setupio(getattr(self._plotter, '_model')))
