#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View for seeing all beads together peaks"
from typing                 import Dict, List
import numpy as np

from bokeh                  import layouts
from bokeh.plotting         import Figure
from bokeh.models           import (ColumnDataSource, Range1d, FactorRange,
                                    NumeralTickFormatter, HoverTool, LinearAxis)
from bokeh.transform        import jitter

from sequences.modelaccess  import SequenceAnaIO
from view.plots             import PlotView
from view.plots.base        import GroupStateDescriptor
from view.plots.ploterror   import PlotError
from view.plots.tasks       import TaskPlotCreator, CACHE_TYPE
from .._model               import resetrefaxis, PeaksPlotTheme
from .._io                  import setupio
from ._model                import (GroupedBeadsScatterModel, GroupedBeadsModelAccess,
                                    GroupedBeadsScatterTheme, GroupedBeadsHistModel,
                                    GroupedBeadsHistTheme, PlotDisplay)
from ._widget               import GroupedBeadsPlotWidgets

ColumnData = Dict[str, np.ndarray]
FigData    = Dict[str, ColumnData]
class GBScatterCreator(TaskPlotCreator[GroupedBeadsModelAccess, GroupedBeadsScatterModel]):
    "Building a scatter plot of beads vs hybridization positions"
    _model:  GroupedBeadsModelAccess
    _theme:  GroupedBeadsScatterTheme
    _src:    Dict[str, ColumnDataSource]
    _fig:    Figure
    _ref:    LinearAxis
    _errors: PlotError
    def _addtodoc(self, *_):
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

        self.linkmodeltoaxes(self._fig)
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
            self.setbounds(cache, self._fig, None, data['events']['bases'])
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
            return {i: np.concatenate(j) if len(j) else [] for i, j in info.items()}

        cols = ('bead', 'bases', 'id', 'orient', 'duration', 'count')
        return {"events": _create(('bead', 'bases'), False),
                "peaks":  _create(cols, True)}

class GBHistCreator(TaskPlotCreator[GroupedBeadsModelAccess, GroupedBeadsHistModel]):
    "Building a histogram for a given peak characteristic"
    _model:     GroupedBeadsModelAccess
    _theme:     GroupedBeadsHistTheme
    _src:       ColumnDataSource
    _peaks:     ColumnDataSource
    _fig:       Figure
    _EMPTY = {i: np.empty(0, dtype = 'f4') for i in ('left', 'top', 'right')}
    def _addtodoc(self, *_):
        self._src = ColumnDataSource(data = self._EMPTY)
        self._fig = self.figure(y_range = Range1d, x_range = FactorRange())
        self.addtofig(
            self._fig, "hist",
            source = self._src,
            bottom = 0,
            **{i: i for i in self._EMPTY}
        )
        self.linkmodeltoaxes(self._fig)
        return self._fig

    def _reset(self, cache: CACHE_TYPE):
        cache[self._src]['data'] = data = self._data()
        self.setbounds(cache, self._fig, data['left'], data['top'])

    def _data(self) -> Dict[str, np.ndarray]:
        items = getattr(self, '_peaks', None)
        if items is None or len(items.data['count']) == 0:
            return self._EMPTY

        vals  = items.data[self._theme.xdata]
        if len(vals):
            sel   = getattr(items.selected, "indices", None)
            if sel is not None:
                vals = vals[sel]

        if len(vals) == 0:
            return self._EMPTY

        rng   = np.nanmax(vals), np.nanmin(vals)
        bsize = self._theme.binsize
        edges = np.arange(int((rng[0]-rng[1])/bsize)+1, dtype = 'f4')*bsize+rng[-1]
        return {
            'left':  edges[:-1],
            'right': edges[1:],
            'y':     np.histogram(vals, bins = edges)[0]
        }

    def setpeaks(self, peaks):
        "sets the peaks data source"
        self._peaks = peaks

        def onselected_cb(attr, old, new):
            "on selected"
            with self.resetting() as cache:
                self._reset(cache)
        peaks.selected.on_change("indices", onselected_cb)

@GroupStateDescriptor(*(f"groupedbeads.plot{i}" for i in ("", ".duration", ".rate")))
class GroupedBeadsPlotCreator(TaskPlotCreator[GroupedBeadsModelAccess, None]):
    "Building scatter & hist plots"
    def __init__(self, ctrl):
        super().__init__(ctrl, addto = False)
        args = {'noerase': False, 'model':   self._model}
        self._scatter  = GBScatterCreator(ctrl, **args)

        args.update(
            theme = GroupedBeadsHistTheme(
                xdata   = "duration",
                binsize = .1,
                xlabel  = PeaksPlotTheme.xtoplabel,
                name    = "groupedbeads.plot.duration"
            ),
            display =  PlotDisplay(name = "groupedbeads.plot.duration")
        )
        self._duration = GBHistCreator(ctrl, **args)

        args.update(
            theme = GroupedBeadsHistTheme(
                xdata   = "count",
                binsize = .5,
                xlabel  = PeaksPlotTheme.xlabel,
                name    = "groupedbeads.plot.rate"
            ),
            display = PlotDisplay(name = "groupedbeads.plot.rate")
        )
        self._rate     = GBHistCreator(ctrl, **args)
        self._widgets  = GroupedBeadsPlotWidgets(ctrl, self._model)
        self.addto(ctrl)

    @property
    def _plots(self):
        return [self._scatter, self._duration, self._rate]

    def observe(self, ctrl):
        "observes the model"
        super().observe(ctrl)
        self._model.setobservers(ctrl)
        self._widgets.observe(ctrl)
        SequenceAnaIO.observe(ctrl)

        @ctrl.display.observe(self._model.sequencemodel.display)
        def _onchangekey(old = None, **_):
            if self.isactive():
                root = self._model.roottask
                if root is not None and {'hpins'} == set(old):
                    self.calllater(lambda: self.reset(False))

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        for i in self._plots:
            i.addto(ctrl, noerase=noerase)

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        plots = [getattr(i, '_addtodoc')(ctrl, doc) for i in self._plots]
        loc   = self._ctrl.theme.get(GroupedBeadsScatterTheme, 'toolbar')['location']
        mode  = self.defaultsizingmode()

        widg  = self._widgets.addtodoc(self, ctrl, doc)
        order = "discarded", "seq", "oligos", "cstrpath"

        grid       = layouts.GridSpec(2, 3)
        grid[0,:]  = plots[0]
        grid[1:,0] = layouts.widgetbox(sum((widg[i] for i in order), []), **mode)
        grid[1:,1] = plots[1:]
        return layouts.gridplot(grid, **mode, toolbar_location = loc)

    def _reset(self, cache:CACHE_TYPE):
        done = 0
        for i in self._plots:
            try:
                i.delegatereset(cache)
                done += 1
            finally:
                pass
        try:
            self._widgets.reset(cache, done != len(self._plots))
        finally:
            pass

@setupio
class GroupedBeadsPlotView(PlotView[GroupedBeadsPlotCreator]):
    "Peaks plot view"
    PANEL_NAME = 'FoV Peaks'
