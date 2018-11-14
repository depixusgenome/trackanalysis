#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View for cleaning data"
from typing                 import Dict, List, cast

import numpy as np

from bokeh                  import layouts
from bokeh.plotting         import Figure
from bokeh.models           import (ColumnDataSource, Range1d, LinearAxis,
                                    NumeralTickFormatter, HoverTool)
from model.plots            import (PlotTheme, PlotDisplay, PlotModel, PlotAttrs,
                                    PlotState)
from peakfinding.histogram  import interpolator
from sequences.modelaccess  import SequenceAnaIO
from utils                  import initdefaults
from view.plots             import PlotView
from view.plots.ploterror   import PlotError
from view.plots.tasks       import TaskPlotCreator, CACHE_TYPE
from ._model                import PeaksPlotModelAccess, createpeaks
from ._widget               import PeaksPlotWidgets, PeakListTheme
from ._io                   import setupio

CurveData = Dict[str, np.ndarray]
HistData  = Dict[str, CurveData]
class CyclePlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name    = "cyclehist.plot.cycle"
    figsize = PlotTheme.defaultfigsize(480, 350)
    xlabel  = 'Time (s)'
    ylabel  = 'Bases'
    ntitles = 5
    frames  = PlotAttrs({"dark": 'lightblue', 'basic': 'darkblue'}, 'line', .1)
    toolbar = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class CyclePlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = CyclePlotTheme()
    display = PlotDisplay(name = "cyclehist.plot.cycle")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class HistPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name     = "cyclehist.plot.hist"
    figsize  = (1000-CyclePlotTheme.figsize[0],)+CyclePlotTheme.figsize[1:]
    xlabel   = 'Rate (%)'
    ylabel   = CyclePlotTheme.ylabel
    explabel = 'Hybridisations'
    reflabel = 'Hairpin'
    hist     = PlotAttrs(CyclePlotTheme.frames.color, 'line',      1)
    events   = PlotAttrs(hist.color,                'circle',    3, alpha = .25)
    peaks    = PlotAttrs(hist.color,                'triangle', 5,  alpha = 0.,
                         angle = np.pi/2.)
    pkcolors = dict(dark  = dict(reference = 'bisque',
                                 missing   = 'red',
                                 found     = 'black'),
                    basic = dict(reference = 'bisque',
                                 missing   = 'red',
                                 found     = 'gray'))
    toolbar          = dict(CyclePlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,hover,reset,save'
    tooltipmode      = 'hline'
    tooltippolicy    = 'follow_mouse'
    tooltips         = [(i[1], '@'+i[0]+("{"+i[2]+"}" if i[2] else ""))
                        for i in PeakListTheme().columns[1:-1]]

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class HistPlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = HistPlotTheme()
    display = PlotDisplay(name = "cyclehist.plot.hist")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class CycleHistPlotState:
    "rh plot state"
    name  = "cyclehist.state"
    state = PlotState.active
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class CyclePlotCreator(TaskPlotCreator[PeaksPlotModelAccess, CyclePlotModel]):
    "Building the graph of cycles"
    _model:  PeaksPlotModelAccess
    _theme:  CyclePlotTheme
    _src:    ColumnDataSource
    _fig:    Figure
    _errors: PlotError
    def _addtodoc(self, ctrl, *_):
        self._src = ColumnDataSource(data = self._data(None))
        self._fig = self.figure(y_range = Range1d, x_range = Range1d)
        self.addtofig(self._fig, 'frames', x = 't', y = 'z', source = self._src)
        self._display.addcallbacks(ctrl, self._fig)
        self._fig.add_layout(LinearAxis(axis_label = ""), 'above')
        self._fig.add_layout(LinearAxis(axis_label = ""), 'right')
        self._fig.yaxis.formatter = NumeralTickFormatter(format = "0.0a")
        self._errors = PlotError(self._fig, self._theme)
        return self._fig

    def _reset(self, cache: CACHE_TYPE):
        def _data():
            procs = self._model.processors()
            if procs is None:
                return None

            evts = self._model.eventdetection.task
            if evts is not None:
                procs = procs.keepupto(evts, False)

            run = next(iter(procs.run(copy = True)))[self._model.bead, ...]
            return list(run.values())

        def _display(items):
            data = self._data(items)
            if (items is not None
                    and self._model.identification.task is not None
                    and len(self._model.distances) == 0):
                self._errors.reset(cache, "Fit unsuccessful!", False)

            self.setbounds(cache, self._fig.x_range, 'x', data['t'])
            self.setbounds(cache, self._fig.y_range, 'y', data['z'])
            cache[self._src]['data'] = data

        self._errors(cache, _data, _display)

    def _data(self, items) -> CurveData:
        if items is None or len(items) == 0 or not any(len(i) for i in items):
            return {"z": [], "t": []}

        lens   = np.cumsum([0]+[len(i)+5 for i in items])
        zval   = np.full(lens[-1]-1, np.NaN, dtype = 'f4')
        tval   = np.full(lens[-1]-1, np.NaN, dtype = 'f4')

        tpatt  = np.arange(max(len(i) for i in items), dtype = 'f4')
        tpatt /= getattr(self._model.track, 'framerate')

        for i, j in zip(lens, items):
            zval[i:i+len(j)] = j
            tval[i:i+len(j)] = tpatt[:len(j)]

        zval = (zval - self._model.bias)*self._model.stretch
        return dict(t = tval, z = zval)

class HistPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, HistPlotModel]):
    "Creates plots for peaks"
    _theme: HistPlotTheme
    _fig: Figure
    _src: Dict[str, ColumnDataSource]
    _exp: LinearAxis
    _ref: LinearAxis
    def _addtodoc(self, ctrl, *_):
        "returns the figure"
        self._fig = self.figure(y_range = Range1d, x_range = Range1d)
        self._exp = LinearAxis(axis_label    = self._theme.explabel)
        self._ref = LinearAxis(axis_label    = self._theme.reflabel)
        self._fig.add_layout(self._exp, 'right')
        self._fig.add_layout(self._ref, 'right')
        self._fig.add_layout(LinearAxis(axis_label = ""), 'above')
        self._fig.yaxis.formatter = NumeralTickFormatter(format = "0.0a")
        self._ref.formatter = NumeralTickFormatter(format = "0a")

        self._src = {i: ColumnDataSource(j) for i, j in self._data(None).items()}
        rends = {i: self.addtofig(self._fig, i,
                                  x      = "count",
                                  y      = 'bases' if i == 'peaks' else "z",
                                  source = j)
                 for i, j in self._src.items()}
        self._display.addcallbacks(ctrl, self._fig)

        hover = self._fig.select(HoverTool)
        if len(hover) > 0:
            hover = hover[0]
            hover.update(point_policy = self._theme.tooltippolicy,
                         tooltips     = self._theme.tooltips,
                         mode         = self._theme.tooltipmode,
                         renderers    = [rends['peaks']])

        return self._fig

    def _reset(self, cache:CACHE_TYPE):
        itms = None
        try:
            itms = self._model.runbead()
        finally:
            data = self._data(itms)
            for i, j in data.items():
                cache[self._src[i]]['data'] = j
            self.setbounds(cache, self._fig.x_range, 'x', data['peaks']['count'])
            self.setbounds(cache, self._fig.y_range, 'y', data['hist']['z'])

            pks = self._model.peaks['bases']
            cache[self._exp]['ticker'] = list(pks[np.isfinite(pks)])

            task = self._model.identification.task
            fit  = getattr(task, 'fit', {}).get(self._model.sequencekey, None)
            if fit is None or len(fit.peaks) <= 2:
                cache[self._ref].update(visible = False)
            else:
                label = self._model.sequencekey
                if not label:
                    label = self._theme.reflabel
                cache[self._ref].update(ticker     = list(fit.peaks[1:-1]),
                                        visible    = True,
                                        axis_label = label)

    def _data(self, itms) -> HistData:
        out: HistData = {i: {"z": [], "count": []} for i in ('hist', 'events')}
        out['peaks']  = createpeaks(self._model, self._theme.pkcolors, None)
        if itms is None:
            return out

        zvals  = itms.binwidth*np.arange(len(itms.histogram), dtype = 'f4')+itms.minvalue
        zvals  = (zvals - self._model.bias) *  self._model.stretch
        cnt    = itms.histogram

        out['hist'].update(z = zvals, count = cnt)

        pos    = (np.concatenate(itms.positions) -self._model.bias)*self._model.stretch
        hmin   = (self._model.fittoreference.hmin-self._model.bias)*self._model.stretch
        out['events'].update(z = pos, count = interpolator(zvals, cnt, hmin)(pos))
        return out

class _StateDescriptor:
    def __get__(self, inst, owner):
        return getattr(inst, '_state').state if inst else self

    @staticmethod
    def setdefault(inst, value):
        "sets the default value"
        getattr(inst, '_ctrl').display.updatedefaults("cyclehist.state", state = PlotState(value))

    def __set__(self, inst, value):
        getattr(inst, '_ctrl').display.update("cyclehist.state", state = PlotState(value))

class _AxisDescriptor:
    name: str
    def __init__(self):
        self.views: List[Figure] = []

    def __set_name__(self, _, name):
        self.name = name

    @property
    def _attr(self):
        return ('major_label_text_font_size' if 'tick' in self.name else
                'grid_line_alpha'            if 'grid' in self.name else
                'axis_label_text_font_size')

    @property
    def _itms(self):
        if 'grid' in self._attr:
            return sum((i.grid for i in self.views), [])
        out  = sum((i.xaxis+i.yaxis for i in self.views), [])
        excl = self.views[0].yaxis[1], self.views[1].yaxis[0]
        return [i for i in out if i not in excl]

    def __get__(self, inst, owner):
        if inst is None:
            return self
        out = getattr(self._itms[0], self._attr)
        return out['value'] if isinstance(out, dict) else out

    def __set__(self, inst, val):
        attr = self._attr
        for i in self._itms:
            if isinstance(getattr(i, attr), dict):
                setattr(i, attr, {"value": val})
            else:
                setattr(i, attr, val)

    def line(self):
        "return the line to display"
        if 'grid' in self.name:
            return "Grid line alpha", f"%({self.name}).2f"
        if 'tick' in self.name:
            return "Tick font size", f"%({self.name})s"
        return "Axis label font size", f"%({self.name})s"

class CycleHistPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, None]):
    "Creates plots for peaks & cycles"
    state = cast(PlotState, _StateDescriptor())
    def __init__(self, ctrl):
        super().__init__(ctrl, addto = False)
        self._cycle   = CyclePlotCreator(ctrl,  noerase = False, model = self._model)
        self._hist    = HistPlotCreator(ctrl, noerase = False, model = self._model)
        self._state   = CycleHistPlotState()
        theme         = PeakListTheme(name = "cyclehist.peak.list", height = 200)
        theme.columns = [i for i in theme.columns if i[0] not in ("z", "skew")]

        self._widgets = PeaksPlotWidgets(ctrl, self._model,
                                         peaks = theme,
                                         title = CycleHistPlotView.PANEL_NAME,
                                         cnf   = getattr(self._cycle, '_plotmodel'),
                                         xaxis = True,
                                         ticksize  = _AxisDescriptor(),
                                         labelsize = _AxisDescriptor(),
                                         gridalpha = _AxisDescriptor()
                                        )
        ctrl.display.add(self._state)
        self.addto(ctrl)

    @property
    def _plots(self):
        return [self._cycle, self._hist]

    def observe(self, ctrl):
        "observes the model"
        assert self._model.sequencemodel.config in ctrl.theme
        super().observe(ctrl)
        assert self._model.sequencemodel.config in ctrl.theme
        self._model.setobservers(ctrl)
        self._widgets.observe(ctrl)
        SequenceAnaIO.observe(ctrl)

        @ctrl.display.observe(self._model.sequencemodel.display)
        def _onchangekey(old = None, **_):
            if ctrl.display.get("cyclehist.state", "state") is PlotState.active:
                root = self._model.roottask
                if root is not None and {'hpins'} == set(old):
                    self.calllater(lambda: self.reset(False))

        @ctrl.theme.observe(getattr(self._cycle, '_theme').name)
        def _onchangefiguresize(old = None, **_):
            if 'figsize' not in old:
                return
            figs    = [(getattr(i, '_fig'), getattr(i, '_theme'))
                       for i in (self._cycle, self._hist)]

            width   = old['figsize'][0] + figs[1][1].figsize[0]-figs[0][1].figsize[0]
            figsize = (width, figs[0][1].figsize[1], figs[1][1].figsize[-1])
            ctrl.theme.update(figs[1][1], figsize = figsize)

            doc     = self._doc
            def _cb(action = 0):
                fig, theme                      = figs[action//2]
                fig.plot_width, fig.plot_height = theme.figsize[:2]
                fig.trigger("sizing_mode", theme.figsize[-1], theme.figsize[-1])
                if action < 1:
                    doc.add_next_tick_callback(lambda: _cb(action+1))
            doc.add_next_tick_callback(_cb)

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        for i in self._plots:
            i.addto(ctrl, noerase=noerase)
        assert self._model.sequencemodel.config in ctrl.theme

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        plots = [getattr(i, '_addtodoc')(ctrl, doc) for i in self._plots]
        for _ in ('ticksize', 'labelsize', 'gridalpha'):
            getattr(self._widgets.advanced.__class__, _).views.extend(plots)

        for i in plots[1:]:
            i.y_range = plots[0].y_range
            i.yaxis[0].update(axis_label = "", major_label_text_font_size = '0pt')
        plots[0].yaxis[1].major_label_text_font_size = '0pt'
        wdg, enabler = self._widgets.addtodoc(self, ctrl, doc,
                                              peaks = getattr(self._hist, '_src')['peaks'])
        enabler.extend([getattr(i, '_fig') for i in self._plots])

        mode     = self.defaultsizingmode()
        order    = [('ref', 'seq', 'fitparams', 'oligos','cstrpath', 'advanced'),
                    ('stats',), ('peaks',)]
        children = [layouts.widgetbox(children = i, **mode)
                    for i in (sum((wdg[i] for i in j), []) # type: ignore
                              for j in order)]
        return self._keyedlayout(ctrl, *plots, bottom = layouts.row(children, **mode))

    def advanced(self):
        "triggers the advanced dialog"
        self._widgets.advanced.on_click()

    def ismain(self, _):
        "specific setup for when this view is the main one"
        self._widgets.advanced.ismain(_)

    def _reset(self, cache:CACHE_TYPE):
        done = 0
        try:
            self._hist.delegatereset(cache)
            done += 1
        finally:
            try:
                self._cycle.delegatereset(cache)
                done += 1
            finally:
                self._widgets.reset(cache, done != 2)

class CycleHistPlotView(PlotView[CycleHistPlotCreator]):
    "Peaks plot view"
    PANEL_NAME = 'Cycles & Peaks'
    TASKS      = 'extremumalignment', 'eventdetection', 'peakselector', 'singlestrand'
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self, ctrl):
        "Alignment, ... is set-up by default"
        self._ismain(ctrl, tasks = self.TASKS,
                     **setupio(getattr(self._plotter, '_model')))