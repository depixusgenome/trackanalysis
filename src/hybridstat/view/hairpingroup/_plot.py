#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View for seeing all beads together peaks"
from functools              import partial
from typing                 import Dict, List
import numpy as np

from bokeh                  import layouts
from bokeh.plotting         import Figure
from bokeh.models           import (ColumnDataSource, Range1d, FactorRange,
                                    NumeralTickFormatter, HoverTool, LinearAxis,
                                    ToolbarBox)
from bokeh.transform        import jitter

from sequences.modelaccess  import SequenceAnaIO
from view.colors            import tohex
from view.plots             import PlotView
from view.plots.base        import GroupStateDescriptor, themed
from view.plots.ploterror   import PlotError
from view.plots.tasks       import TaskPlotCreator, CACHE_TYPE
from .._model               import resetrefaxis, PeaksPlotTheme
from .._io                  import setupio
from ._model                import (HairpinGroupScatterModel, HairpinGroupModelAccess,
                                    HairpinGroupScatterTheme, HairpinGroupHistModel,
                                    HairpinGroupHistTheme, PlotDisplay)
from ._widget               import HairpinGroupPlotWidgets

ColumnData = Dict[str, np.ndarray]
FigData    = Dict[str, ColumnData]
class GBScatterCreator(TaskPlotCreator[HairpinGroupModelAccess, HairpinGroupScatterModel]):
    "Building a scatter plot of beads vs hybridization positions"
    _model:  HairpinGroupModelAccess
    _theme:  HairpinGroupScatterTheme
    _src:    Dict[str, ColumnDataSource]
    _fig:    Figure
    _ref:    LinearAxis
    _errors: PlotError
    def create(self):
        "add to doc"
        self._src = {i: ColumnDataSource(data = j) for i, j in self._data(None).items()}
        self._fig = self.figure(y_range   = Range1d, x_range = FactorRange())
        self._fig.grid[0].grid_line_alpha = self._theme.xgridalpha
        self._ref = LinearAxis(axis_label = self._theme.reflabel,
                               formatter  = NumeralTickFormatter(format = "0"))
        self._fig.add_layout(self._ref, 'right')

        jtr       = jitter("bead", range = self._fig.x_range, width = .75)
        self.addtofig(self._fig, "events", x = jtr, y = 'bases',
                      source = self._src["events"])
        self.addtofig(self._fig, "hpin",  x = "bead", y = 'bases', source = self._src["hpin"])
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

    def _addtodoc(self, *_):
        raise NotImplementedError()

    @property
    def peaks(self):
        "return the source for peaks"
        return self._src['peaks']

    def _reset(self, cache: CACHE_TYPE):
        def _data():
            return self._model.runbead()

        def _display(items):
            data  = self._data(items)
            beads = [i for i in sorted(int(i) for i in set(data['events']['bead']))]
            bead  = self._model.bead
            if bead in beads:
                beads.remove(bead)
                beads.insert(0, bead)

            cache[self._fig.x_range].update(factors = [str(i) for i in beads])
            self.setbounds(cache, self._fig, None, data['events']['bases'])
            cache[self._ref] = resetrefaxis(self._model, self._theme.reflabel)
            for i, j in data.items():
                cache[self._src[i]]['data'] = j

        self._errors(cache, _data, _display)

    def _data(self, items) -> FigData:
        if items is None:
            items = {}

        cols = ('bead', 'bases', 'id', 'orient', 'duration', 'count')
        out  = {"events": self.__exp(items, ('bead', 'bases'), False),
                "peaks":  self.__exp(items, cols, True),
                'hpin':   self.__hpin(items)}
        return out

    @staticmethod
    def __exp(items, cols, itr):
        info: Dict[str, List[np.ndarray]] = {i: [] for i in cols}
        for i, _ in items.items():
            j = _[itr]
            if isinstance(j, dict):
                for k in cols:
                    if k != 'bead':
                        info[k].append(j[k])
            else:
                info["bases"].append(j)
            info['bead'].append(np.full(len(info["bases"][-1]), str(i), dtype='<U3'))
        return {i: np.concatenate(j) if len(j) else [] for i, j in info.items()}

    def __hpin(self, items):
        task  = self._model.identification.task
        fit   = getattr(task, 'fit', {}).get(self._model.sequencekey, None)
        beads = np.sort(list(items))
        if fit is not None and len(fit.peaks) > 0 and len(beads) > 0:
            return {'bead':  np.repeat(beads, len(fit.peaks)).astype('<U3'),
                    'bases': np.concatenate([fit.peaks]*len(beads)),
                    'color': self.__hpincolors(beads, items, fit.peaks)}
        return {'bead': [], 'bases': [], "color": []}

    def __hpincolors(self, beads, items, fitpeaks):
        colors = tohex(themed(self, self._theme.pkcolors))
        arr    = np.array([colors['missing']]*len(beads)*len(fitpeaks))
        for ibead, cache in items.items():
            izero = np.searchsorted(beads, ibead)*len(fitpeaks)
            found = cache[1]['id'][np.isfinite(cache[1]['id'])].astype('i4')
            arr[np.searchsorted(fitpeaks,found)+izero] = colors['found']
        return arr

class GBHistCreator(TaskPlotCreator[HairpinGroupModelAccess, HairpinGroupHistModel]):
    "Building a histogram for a given peak characteristic"
    _model:     HairpinGroupModelAccess
    _theme:     HairpinGroupHistTheme
    _src:       ColumnDataSource
    _peaks:     ColumnDataSource
    _fig:       Figure
    _EMPTY = {i: np.empty(0, dtype = 'f4') for i in ('left', 'top', 'right')}
    def create(self):
        "add to doc"
        self._src = ColumnDataSource(data = self._EMPTY)
        self._fig = self.figure(y_range = Range1d, x_range = Range1d)
        self.addtofig(
            self._fig, "hist",
            source = self._src,
            bottom = 0,
            **{i: i for i in self._EMPTY}
        )
        self.linkmodeltoaxes(self._fig)
        return self._fig

    def _addtodoc(self, *_):
        raise NotImplementedError()

    def _reset(self, cache: CACHE_TYPE):
        cache[self._src]['data'] = data = self._data(cache)
        if len(data['left']):
            bsize = self._theme.binsize
            xbnds = [data['left'][0]-bsize, data['right'][-1]+bsize]
            ybnds = [0, np.max(data['top'])+1]
        else:
            xbnds = []
            ybnds = []
        self.setbounds(cache, self._fig, xbnds, ybnds)

    def _data(self, cache) -> Dict[str, np.ndarray]:
        data = self._peaks.data
        if self._peaks in cache:
            data = cache[self._peaks].get("data", self._peaks.data)

        if len(data['count']) == 0:
            return self._EMPTY

        vals  = data[self._theme.xdata]
        if len(vals):
            sel = self._peaks.selected
            if self._peaks in cache and 'selected' in cache[self._peaks]:
                sel = cache[self._peaks]["selected"]
            if sel in cache and "indices" in cache[sel]:
                inds = cache[sel]["indices"]
            else:
                inds = getattr(sel, "indices", None)
            if inds:
                vals = vals[inds]

        if len(vals) == 0:
            return self._EMPTY

        rng   = np.nanmax(vals), np.nanmin(vals)
        bsize = self._theme.binsize
        edges = np.arange(int((rng[0]-rng[1])/bsize)+1, dtype = 'f4')*bsize+rng[-1]
        return {
            'left':  edges[:-1],
            'right': edges[1:],
            'top':   np.histogram(vals, bins = edges)[0]
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
class HairpinGroupPlotCreator(TaskPlotCreator[HairpinGroupModelAccess, None]):
    "Building scatter & hist plots"
    def __init__(self, ctrl):
        super().__init__(ctrl, addto = False)
        args = {'noerase': False, 'model':   self._model}
        self._scatter  = GBScatterCreator(ctrl, **args)

        args.update(
            theme = HairpinGroupHistTheme(
                xdata   = "duration",
                binsize = .2,
                xlabel  = PeaksPlotTheme.xtoplabel,
                name    = "groupedbeads.plot.duration"
            ),
            display =  PlotDisplay(name = "groupedbeads.plot.duration")
        )
        self._duration = GBHistCreator(ctrl, **args)

        args.update(
            theme = HairpinGroupHistTheme(
                xdata   = "count",
                binsize = 2.,
                xlabel  = PeaksPlotTheme.xlabel,
                name    = "groupedbeads.plot.rate"
            ),
            display = PlotDisplay(name = "groupedbeads.plot.rate")
        )
        self._rate     = GBHistCreator(ctrl, **args)
        self._widgets  = HairpinGroupPlotWidgets(ctrl, self._model)
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

        @ctrl.display.observe
        def _ongroupedbeads(**_):
            if self.isactive():
                self.reset(False)

        curr = [False]
        name = HairpinGroupScatterTheme().name

        def _reset():
            curr[0] = False
            self._doc.add_next_tick_callback(partial(self.reset, False))

        @ctrl.display.observe("hybridstat.peaks.store")
        def _on_store(**_):
            if self.isactive() and not curr[0]:
                curr[0] = True
                time    = self._ctrl.theme.get(name, "displaytimeout")
                self._doc.add_timeout_callback(_reset, time)

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        for i in self._plots:
            i.addto(ctrl, noerase=noerase)

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        plots = [i.create() for i in self._plots]
        self._duration.setpeaks(self._scatter.peaks)
        self._rate    .setpeaks(self._scatter.peaks)
        def _update_cb(attr, old, new):
            if self.isactive():
                self._duration.reset(False)
                self._rate.reset(False)
        self._scatter.peaks.selected.on_change('indices', _update_cb)

        loc   = self._ctrl.theme.get(HairpinGroupScatterTheme, 'toolbar')['location']
        mode  = self.defaultsizingmode()

        widg  = self._widgets.addtodoc(self, ctrl, doc)
        order = "discarded", "seq", "oligos", "cstrpath"
        wbox  = layouts.widgetbox(sum((widg[i] for i in order), []), **mode)

        hists = layouts.gridplot([plots[1:]], **mode, toolbar_location = loc)
        # pylint: disable=not-an-iterable
        tbar  = next(i for i in hists.children if isinstance(i, ToolbarBox))
        tbar.toolbar.logo = None
        return layouts.layout([[plots[0]], [wbox, hists]], **mode)

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
class HairpinGroupPlotView(PlotView[HairpinGroupPlotCreator]):
    "Peaks plot view"
    PANEL_NAME = 'Hairpin Groups'
