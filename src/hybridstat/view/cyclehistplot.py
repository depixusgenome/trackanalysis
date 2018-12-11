#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View for seeing both cycles and peaks"
from copy                   import deepcopy
from typing                 import Dict, cast

import numpy as np

from bokeh                  import layouts
from bokeh.plotting         import Figure
from bokeh.models           import (ColumnDataSource, Range1d, LinearAxis,
                                    NumeralTickFormatter, HoverTool)
from model.level            import PHASE
from model.plots            import (PlotTheme, PlotDisplay, PlotModel, PlotAttrs,
                                    PlotState)
from peakfinding.histogram  import interpolator
from sequences.modelaccess  import SequenceAnaIO
from utils                  import initdefaults
from view.plots             import PlotView
from view.plots.ploterror   import PlotError
from view.plots.tasks       import TaskPlotCreator, CACHE_TYPE
from ._model                import (PeaksPlotModelAccess, PeaksPlotTheme,
                                    createpeaks, resetrefaxis)
from ._widget               import PeaksPlotWidgets, PeakListTheme
from ._io                   import setupio

CurveData = Dict[str, np.ndarray]
HistData  = Dict[str, CurveData]
class CyclePlotTheme(PlotTheme):
    "cycles & peaks plot theme: cycles"
    name      = "cyclehist.plot.cycle"
    figsize   = PlotTheme.defaultfigsize(530, 300)
    phasezoom = PHASE.measure, 20
    fiterror  = PeaksPlotTheme.fiterror
    xlabel    = PlotTheme.xtoplabel
    ylabel    = PlotTheme.yrightlabel
    ntitles   = 5
    format    = '0.0a'
    frames    = PlotAttrs('~gray', '-', 1., alpha=.25)
    points    = PlotAttrs(deepcopy(PeaksPlotTheme.count.color), 'o', 1, alpha=.5)
    toolbar   = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,wheel_zoom,reset,save'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class CyclePlotModel(PlotModel):
    "cycles & peaks plot model: cycles"
    theme   = CyclePlotTheme()
    display = PlotDisplay(name = "cyclehist.plot.cycle")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class HistPlotTheme(PlotTheme):
    "cycles & peaks plot theme: histogram"
    name     = "cyclehist.plot.hist"
    figsize          = (1000-CyclePlotTheme.figsize[0],)+CyclePlotTheme.figsize[1:]
    xlabel           = PeaksPlotTheme.xlabel
    ylabel           = CyclePlotTheme.ylabel
    explabel         = 'Hybridisations'
    reflabel         = 'Hairpin'
    formats          = {'bases': '0.0a', 'ref': '0', 'exp': '0.0'}
    hist             = deepcopy(PeaksPlotTheme.count)
    events           = PlotAttrs(hist.color, 'o', 3, alpha = .25)
    peaks            = PlotAttrs(hist.color, '△', 5, alpha = 0., angle = np.pi/2.)
    pkcolors         = deepcopy(PeaksPlotTheme.pkcolors)
    minzoomz         = .008
    toolbar          = dict(CyclePlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,wheel_zoom,hover,reset,save'
    tooltipmode      = 'hline'
    tooltippolicy    = 'follow_mouse'
    tooltips         = [(i[1], '@'+i[0]+("{"+i[2]+"}" if i[2] else ""))
                        for i in PeakListTheme().columns[1:-1]]

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class HistPlotModel(PlotModel):
    "cycles & peaks plot plot model: histogram"
    theme   = HistPlotTheme()
    display = PlotDisplay(name = "cyclehist.plot.hist")
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__()

class CyclePlotCreator(TaskPlotCreator[PeaksPlotModelAccess, CyclePlotModel]):
    "Building the graph of cycles"
    _model:  PeaksPlotModelAccess
    _theme:  CyclePlotTheme
    _src:    ColumnDataSource
    _fig:    Figure
    _errors: PlotError
    def _addtodoc(self, ctrl, doc, *_): # pylint: disable=unused-argument
        self._src  = ColumnDataSource(data = self._data(None))
        self._fig  = self.figure(y_range = Range1d, x_range = Range1d)
        self.addtofig(self._fig, 'frames', x = 't', y = 'z', source = self._src)
        self.addtofig(self._fig, 'points', x = 't', y = 'z', source = self._src)
        self.linkmodeltoaxes(self._fig)
        self._fig.add_layout(LinearAxis(axis_label = ""), 'above')
        self._fig.add_layout(LinearAxis(axis_label = ""), 'right')
        self._fig.yaxis.formatter = NumeralTickFormatter(format = self._theme.format)
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
            if items is not None and self._model.fiterror():
                self._errors.reset(cache, self._theme.fiterror, False)

            self.__setbounds(cache, data)
            cache[self._src]['data'] = data

        self._errors(cache, _data, _display)

    def __setbounds(self, cache, data):
        if (self._theme.phasezoom and self._theme.phasezoom[0] and len(data['z']) > 0):
            pha, delta = self._theme.phasezoom
            trk        = self._model.track
            tx1        = trk.phase.duration(..., range(0,pha)).mean()   - delta
            tx2        = trk.phase.duration(..., range(0,pha+1)).mean() + delta

            xvals      = [fcn(data['t']) for fcn in (np.nanmin, np.nanmax)]
            xbnds      = [tx1/trk.framerate, tx2/trk.framerate]
            yvals      = data['z']
            ybnds      = data['z'][(data['t'] >= xbnds[0]) & (data['t'] <= xbnds[1])]

            task       = self._model.identification.task
            fit        = getattr(task, 'fit', {}).get(self._model.sequencekey, None)
            if fit and len(fit.peaks):
                yvals  = [fcn(yvals) for fcn in (np.nanmin, np.nanmax)]+list(fit.peaks)
                ybnds  = [fcn(ybnds) for fcn in (np.nanmin, np.nanmax) if len(ybnds)]
                ybnds += list(fit.peaks)
        else:
            xbnds = ybnds = xvals = yvals = []

        self.setbounds(cache, self._fig, xvals, yvals, xbnds, ybnds)

    def _data(self, items) -> CurveData:
        if items is None or len(items) == 0 or not any(len(i) for i in items):
            return {"z": [], "t": []}

        lens   = np.cumsum([0]+[len(i)+2 for i in items])
        zval   = np.full(lens[-1]-1, np.NaN, dtype = 'f4')
        tval   = np.zeros(lens[-1]-1, dtype = 'f4')

        tpatt  = np.arange(max(len(i) for i in items), dtype = 'f4')
        tpatt /= getattr(self._model.track, 'framerate')

        for i, j in zip(lens, items):
            zval[i:i+len(j)] = j
            tval[i:i+len(j)] = tpatt[:len(j)]

        zval = (zval - self._model.bias)*self._model.stretch
        return dict(t = tval, z = zval)

class HistPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, HistPlotModel]):
    "Creates a histogram of peaks"
    _theme: HistPlotTheme
    _fig: Figure
    _src: Dict[str, ColumnDataSource]
    _exp: LinearAxis
    _ref: LinearAxis
    def _addtodoc(self, ctrl, doc, *_): # pylint: disable=unused-argument
        "returns the figure"
        self._fig = self.figure(y_range = Range1d, x_range = Range1d)
        self._exp = LinearAxis(axis_label    = self._theme.explabel)
        self._ref = LinearAxis(axis_label    = self._theme.reflabel)
        self._fig.add_layout(self._exp, 'right')
        self._fig.add_layout(self._ref, 'right')
        self._fig.add_layout(LinearAxis(axis_label = ""), 'above')

        fmts = self._theme.formats
        self._fig.yaxis[0].formatter = NumeralTickFormatter(format = fmts['bases'])
        self._exp.formatter          = NumeralTickFormatter(format = fmts['exp'])
        self._ref.formatter          = NumeralTickFormatter(format = fmts['ref'])

        self._src = {i: ColumnDataSource(j) for i, j in self._data(None).items()}
        rends = {i: self.addtofig(self._fig, i,
                                  x      = "count",
                                  y      = 'bases' if i == 'peaks' else "z",
                                  source = j)
                 for i, j in self._src.items()}
        self.linkmodeltoaxes(self._fig)

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

            xarr  = data['peaks']['count']
            xarr  = xarr[np.isfinite(xarr)]
            xarr  = [0., xarr.max() if len(xarr) else 1.]

            pks   = data['peaks']['z']
            xbnds = np.empty(0, dtype = 'f4')
            if len(pks) > 1:
                xbnds = data['peaks']['count'][pks > pks[0] + self._theme.minzoomz]
                xbnds = xbnds[np.isfinite(xbnds)]
            xbnds = [0., xbnds.max() if len(xbnds) else 1.]

            self.setbounds(cache, self._fig, xarr, data['hist']["z"], xbnds)

            pks = self._model.peaks['bases']
            cache[self._exp]['ticker'] = list(pks[np.isfinite(pks)])
            cache[self._ref] = resetrefaxis(self._model, self._theme.reflabel)
            task = self._model.identification.task
            fit  = getattr(task, 'fit', {}).get(self._model.sequencekey, None)
            if fit is None or len(fit.peaks) <= 0:
                cache[self._ref].update(visible = False)
            else:
                label = self._model.sequencekey
                if not label:
                    label = self._theme.reflabel
                cache[self._ref].update(ticker     = list(fit.peaks),
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

        pos  = (np.concatenate(itms.positions) -self._model.bias)*self._model.stretch
        hmin = np.median(cnt)/100
        out['events'].update(z = pos, count = interpolator(zvals, cnt, hmin)(pos))
        return out

class _StateDescriptor:
    def __get__(self, inst, owner):
        if inst is None:
            return self
        return getattr(inst, '_ctrl').display.get("cyclehist.plot.hist", 'state')

    @staticmethod
    def setdefault(inst, value):
        "sets the default value"
        state = PlotState(value)
        fcn   = getattr(inst, '_ctrl').display.updatedefaults
        fcn("cyclehist.plot.hist",  state = state)
        fcn("cyclehist.plot.cycle", state = state)

    def __set__(self, inst, value):
        state = PlotState(value)
        fcn   = getattr(inst, '_ctrl').display.update
        fcn("cyclehist.plot.hist",  state = state)
        fcn("cyclehist.plot.cycle", state = state)

class CycleHistPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, None]):
    "Creates plots for peaks & cycles"
    state = cast(PlotState, _StateDescriptor())
    def __init__(self, ctrl):
        super().__init__(ctrl, addto = False)
        self._cycle   = CyclePlotCreator(ctrl,  noerase = False, model = self._model)
        self._hist    = HistPlotCreator(ctrl, noerase = False, model = self._model)
        theme         = PeakListTheme(name = "cyclehist.peak.list", height = 200)
        theme.columns = [i for i in theme.columns if i[0] not in ("z", "skew")]

        args = dict(text = """
                       Cycle lines alpha    %(CyclePlotTheme:frames.alpha).2f
                       Grid line alpha      %(theme.grid_line_alpha).2f
                       Font                 %(theme.font)s
                       Tick font size       %(theme.major_label_text_font_size)s
                       Axis label font size %(theme.axis_label_text_font_size)s
                       """,
                    peaks     = theme,
                    cnf       = getattr(self._cycle, '_plotmodel'),
                    accessors = (CyclePlotTheme,),
                    xaxis     = True)
        self._widgets = PeaksPlotWidgets(ctrl, self._model, **args)
        self.addto(ctrl)

    @property
    def _plots(self):
        return [self._cycle, self._hist]

    def observe(self, ctrl, noerase = True):
        "observes the model"
        super().observe(ctrl, noerase = noerase)
        self._model.setobservers(ctrl)
        self._widgets.observe(ctrl)
        SequenceAnaIO.observe(ctrl)

        ctrl.theme.observe(CyclePlotTheme.name, lambda **_: self.reset(False))

        @ctrl.display.observe(self._model.sequencemodel.display)
        def _onchangekey(old = None, **_):
            if self.isactive():
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

    def _addtodoc(self, ctrl, doc, *_):
        "returns the figure"
        plots = [getattr(i, '_addtodoc')(ctrl, doc) for i in self._plots]
        for i in plots[1:]:
            i.y_range = plots[0].y_range
            i.yaxis[0].update(axis_label = "", major_label_text_font_size = '0pt')

        # add a grid to the advanced menu because some themes are missing
        # a grid_line_alpha attribute
        attr = getattr(type(self._widgets.advanced), 'theme1')
        attr.items.append(plots[0].grid[0])

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
    TASKS      = ('extremumalignment', 'clipping', 'eventdetection', 'peakselector',
                  'singlestrand')
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self, ctrl):
        "Alignment, ... is set-up by default"
        self._ismain(ctrl, tasks = self.TASKS,
                     **setupio(getattr(self._plotter, '_model')))
