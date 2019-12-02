#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View for seeing both cycles and peaks"
from copy                   import deepcopy
from typing                 import Dict, List, Tuple, TypeVar, Optional, Any, cast

import numpy as np

from bokeh                     import layouts
from bokeh.plotting            import Figure
from bokeh.models              import (
    ColumnDataSource, Range1d, LinearAxis, NumeralTickFormatter, HoverTool, LayoutDOM
)
from cleaning.view             import GuiDataCleaningProcessor
from cleaning.processor        import DataCleaningException
from model.maintheme           import AppTheme
from model.plots               import (PlotTheme, PlotDisplay, PlotModel, PlotAttrs,
                                       PlotState)
from peakfinding.histogram     import interpolator
from taskview.plots            import (
    PlotError, PlotView, TaskPlotCreator, PlotModelType, CACHE_TYPE
)
from tasksequences.modelaccess import SequenceAnaIO
from utils                     import initdefaults
from ._model                   import (PeaksPlotModelAccess, PeaksPlotTheme,
                                       createpeaks, resetrefaxis)
from ._widget                  import PeaksPlotWidgets, PeakListTheme
from ._io                      import setupio


CurveData    = Dict[str, np.ndarray]
HistData     = Dict[str, CurveData]
TModelAccess = TypeVar('TModelAccess', bound = PeaksPlotModelAccess)


class CyclePlotTheme(PlotTheme):
    "cycles & peaks plot theme: cycles"
    name:      str                  = "cyclehist.plot.cycle"
    figsize:   Tuple[int, int, str] = (300, 497, 'fixed')
    phasezoom: int                  = 20
    fiterror:  str                  = PeaksPlotTheme.fiterror
    xlabel:    str                  = PlotTheme.xtoplabel
    ylabel:    str                  = PlotTheme.yrightlabel
    ntitles:   int                  = 5
    format:    str                  = '0.0a'
    frames:    PlotAttrs            = PlotAttrs(
        '~gray', '-', 1., alpha = .25
    )
    points:    PlotAttrs            = PlotAttrs(
        deepcopy(PeaksPlotTheme.count.color), 'o', 1, alpha = .5
    )
    toolbar:   Dict[str, Any]       = dict(
        PlotTheme.toolbar, items = 'pan,box_zoom,wheel_zoom,reset,save'
    )

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
    figsize          = (
        AppTheme().appsize[0]-CyclePlotTheme.figsize[0],  # pylint: disable=unsubscriptable-object
        * CyclePlotTheme.figsize[1:]
    )
    xlabel           = PeaksPlotTheme.xlabel
    ylabel           = CyclePlotTheme.ylabel
    explabel         = 'Hybridisations'
    reflabel         = 'Hairpin'
    formats          = {'bases': '0.0a', 'ref': '0', 'exp': '0.0'}
    hist             = deepcopy(PeaksPlotTheme.count)
    events           = PlotAttrs(
        hist.color, 'o', 4,
        alpha           = .25,
        selection_alpha = 1.,
        selection_color = '~green'
    )
    peaks            = PlotAttrs(hist.color, '△', 5, alpha = 0., angle = np.pi/2.)
    pkcolors         = deepcopy(PeaksPlotTheme.pkcolors)
    minzoomz: Optional[float] = .008/.88e-3
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
    plot  = cast(Figure,           property(lambda self: self._fig))

    def __init__(self, ctrl, **_):
        super().__init__(ctrl, **_)
        self.addto(ctrl)

    def _addtodoc(self, ctrl, doc, *_):  # pylint: disable=unused-argument
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
        def _data() -> Optional[Tuple[List[np.ndarray], Optional[Exception]]]:
            procs = self._model.processors()
            if procs is None:
                return None

            evts = self._model.eventdetection.task
            if evts is not None:
                procs = procs.keepupto(evts, False)

            try:
                return list(next(procs.run())[self._model.bead, ...].values()), None
            except DataCleaningException:
                itms, _, exc = GuiDataCleaningProcessor.runbead(self._model, ctrl = procs)
                return [i for _, i in itms], exc

        def _display(items: Optional[Tuple[List[np.ndarray], Optional[Exception]]]):
            data = self._data(items[0] if items else None)
            if items and items[1]:
                self._errors.reset(cache, items[1])
            elif items is not None and self._model.fiterror():
                self._errors.reset(cache, self._theme.fiterror, False)

            self.__setbounds(cache, data)
            cache[self._src]['data'] = data

        self._errors(cache, _data, _display)

    def __setbounds(self, cache, data):
        if self._theme.phasezoom and len(data['z']) > 0:
            pha        = self._model.eventdetection.task.phase
            delta      = self._theme.phasezoom
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


class BaseHistPlotCreator(TaskPlotCreator[TModelAccess, PlotModelType]):
    "Creates a histogram of peaks"
    _plotmodel: PlotModelType
    _model:     TModelAccess
    _theme:     HistPlotTheme
    _fig:       Figure
    _src:       Dict[str, ColumnDataSource]
    _exp:       LinearAxis
    _ref:       LinearAxis
    peaksdata = cast(ColumnDataSource, property(lambda self: self._src['peaks']))
    plot      = cast(Figure,           property(lambda self: self._fig))

    def _addtodoc(self, ctrl, doc, *_):  # pylint: disable=unused-argument
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
                                  y      = 'bases',
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

            xarr  = data['hist']['count']
            if len(xarr):
                xarr  = xarr[np.isfinite(xarr)]
            xarr  = [0., xarr.max() if len(xarr) else 1.]

            pks   = data['peaks']['bases']
            xbnds = np.empty(0, dtype = 'f4')
            if len(pks) > 1 and self._theme.minzoomz is not None:
                minv  = pks.min() + self._theme.minzoomz-data['hist']['bases'][0]
                delta = np.diff(self._theme.minzoomz-data['hist']['bases'][:2])[0]
                xbnds = data['hist']['count'][1-int(minv/delta):]
            else:
                xbnds = data['hist']['count']
            xbnds = [0., xbnds.max() if len(xbnds) else 1.]

            self.setbounds(cache, self._fig, xarr, data['hist']["bases"], xbnds)

            cache[self._exp]['ticker'] = list(pks[np.isfinite(pks)]) if len(pks) else []
            cache[self._ref] = resetrefaxis(self._model, self._theme.reflabel)
            task = self._model.identification.task
            fit  = getattr(task, 'fit', {}).get(self._model.sequencekey, None)
            if itms is None or fit is None or len(fit.peaks) <= 0:
                cache[self._ref].update(visible = False)
            else:
                label = self._model.sequencekey
                if not label:
                    label = self._theme.reflabel
                cache[self._ref].update(ticker     = list(fit.peaks),
                                        visible    = True,
                                        axis_label = label)

    def _data(self, itms) -> HistData:
        out: HistData = {i: {"bases": [], "count": []} for i in ('hist', 'events')}
        self._createpeaks(itms, out)
        if itms is None:
            return out

        zvals  = itms.binwidth*np.arange(len(itms.histogram), dtype = 'f4')+itms.minvalue
        zvals  = self._tobases(zvals)
        cnt    = itms.histogram

        out['hist'].update(bases = zvals, count = cnt)

        interp = interpolator(zvals, cnt, np.median(cnt)/100)
        out['events'].update(count = interp(out['events']['bases']))
        return out

    def _createpeaks(self, itms, out):
        out['peaks']           = createpeaks(self._model, self._theme.pkcolors, None)
        if itms is not None:
            out['events']['bases'] = self._tobases(np.concatenate(itms.positions))
        return False

    def _tobases(self, arr):
        return (arr-self._model.bias)*self._model.stretch


class HistPlotCreator(BaseHistPlotCreator[PeaksPlotModelAccess,  # type: ignore
                                          HistPlotModel]):
    "Creates a histogram of peaks"
    def __init__(self, ctrl, **_):
        super().__init__(ctrl, **_)
        self.addto(ctrl)

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


class CycleHistPlotWidgets(PeaksPlotWidgets):
    "PeaksPlotWidgets with a different layout"
    @staticmethod
    def resize(sizer, borders:int, width:int):  # pylint: disable=arguments-differ
        "resize elements in the sizer"
        stats = sizer.children[1].children[0]
        pks   = sizer.children[2].children[0]
        for i in sizer.children[0].children:
            i.width = width - pks.width - stats.width - borders
        for i in sizer.children:
            i.update(
                width  = max(j.width  for j in i.children),
                height = sum(j.height for j in i.children)
            )

        sizer.children[0].width += borders
        sizer.update(
            width  = sum(i.width  for i in sizer.children),
            height = max(i.height for i in sizer.children)+borders,
        )

    @classmethod
    def _assemble(cls, mode, wdg):
        # pylint: disable=unsubscriptable-object
        out  = super()._assemble(mode, wdg)
        return layouts.row(
            [*out.children[0].children, out.children[1]],
            **mode
        )


class CycleHistPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, None]):
    "Creates plots for peaks & cycles"
    state = cast(PlotState, _StateDescriptor())

    def __init__(self, ctrl):
        super().__init__(ctrl)
        self._cycle   = CyclePlotCreator(ctrl, model = self._model)
        self._hist    = HistPlotCreator(ctrl, model = self._model)
        theme         = PeakListTheme(name = "cyclehist.peak.list", height = 200)
        theme.columns = [i for i in theme.columns if i[0] not in ("z", "skew")]

        args = dict(text = """
                       Cycle lines alpha    %(CyclePlotTheme:frames.alpha).2f
                       Grid line alpha      %(theme.grid_line_alpha).2f
                       Font                 %(theme.font)os
                       Tick font size       %(theme.major_label_text_font_size)os
                       Axis label font size %(theme.axis_label_text_font_size)os
                       """,
                    peaks     = theme,
                    cnf       = getattr(self._cycle, '_plotmodel'),
                    accessors = (CyclePlotTheme,),
                    xaxis     = True)

        self._widgets = CycleHistPlotWidgets(ctrl, self._model, **args)
        self.addto(ctrl)

    _plots      = cast(
        Tuple[CyclePlotCreator, HistPlotCreator],
        property(lambda self: (self._cycle, self._hist))
    )
    plotfigures = cast(
        Tuple[Figure, Figure],
        property(lambda self: (self._cycle.plot, self._hist.plot))
    )
    peaksdata    = cast(ColumnDataSource, property(lambda self: self._hist.peaksdata))
    plottheme    = cast(PeaksPlotTheme,   property(lambda self: self._theme))

    def observe(self, ctrl):
        "observes the model"
        super().observe(ctrl)
        self._widgets.observe(ctrl)
        SequenceAnaIO.observe(ctrl)

        ctrl.theme.observe(CyclePlotTheme.name, lambda **_: self.reset(False))

        @ctrl.display.observe(self._model.sequencemodel.display)
        def _onchangekey(old = None, **_):
            if self.isactive():
                root = self._model.roottask
                if root is not None and {'hpins'} == set(old):
                    self.calllater(lambda: self.reset(False))

    def addto(self, ctrl):
        "adds the models to the controller"
        for i in self._plots:
            i.addto(ctrl)
        self._model.addto(ctrl)

    def _addtodoc(self, ctrl, doc, *_) -> LayoutDOM:
        "returns the figure"
        for i in self._plots:
            getattr(i, '_addtodoc')(ctrl, doc)
        self._hist.plot.y_range = self._cycle.plot.y_range
        self._hist.plot.yaxis[0].update(axis_label = "", major_label_text_font_size = '0pt')
        self._cycle.plot.yaxis[1].major_label_text_font_size = '0pt'

        bottom = self._widgets.addtodoc(self, ctrl, doc)
        out    = self._keyedlayout(ctrl, *self.plotfigures, bottom = bottom)
        self.__resize(ctrl, out, bottom, True)

        theme = getattr(self._cycle, '_theme')
        sizes = (
            self._cycle.plot.plot_width,
            self._cycle.plot.plot_height,
            self._cycle.plot.sizing_mode
        )
        ctrl.theme.update(theme, figsize = sizes)

        @ctrl.theme.observe(getattr(self._cycle, '_theme').name)
        def _onchangefiguresize(old = None, model = None, **_):
            if 'figsize' not in old:
                return
            self._cycle.plot.plot_width = model.figsize[0]
            self._hist.plot.plot_width  = out.width-model.figsize[0]
            out.height = bottom.height+model.figsize[1]+ctrl.theme.get('theme', 'figtbheight')
            self.__resize(ctrl, out, bottom, False)
        return out

    def advanced(self):
        "triggers the advanced dialog"
        self._widgets.advanced.on_click()

    def ismain(self, _):
        "specific setup for when this view is the main one"
        self._widgets.advanced.ismain(_)

    def _reset(self, cache:CACHE_TYPE):
        try:
            self._hist.delegatereset(cache)
        finally:
            try:
                self._cycle.delegatereset(cache)
            finally:
                self._widgets.reset(cache, self._model.track is None)

    def __resize(self, ctrl, sizer, bottom, doresize):
        borders            = ctrl.theme.get('theme', "borders")
        tsz                = self.defaulttabsize(ctrl)
        tsz['sizing_mode'] = self._cycle.plot.sizing_mode

        self._widgets.resize(bottom, borders, tsz['width'])
        if doresize:
            sizer.update(**tsz)
        for fig in self.plotfigures:
            height = (
                sizer.height - ctrl.theme.get('theme', 'figtbheight') - bottom.height
            )

            fig.update(plot_height  = height)
        self._hist.plot.update(plot_width = sizer.width - self._cycle.plot.plot_width)
        for i in (sizer.children[0], sizer.children[0].children[0]):
            i.update(
                width  = sizer.width,
                height = sizer.height - bottom.height
            )


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
