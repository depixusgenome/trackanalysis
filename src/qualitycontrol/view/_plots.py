#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Provides plots for temperatures and bead extensions"
import warnings
from   typing               import Dict, Optional, Tuple, List, cast

from   bokeh                import layouts
from   bokeh.models         import ColumnDataSource, Range1d
from   bokeh.plotting       import Figure
import numpy                as     np

from   data                 import Beads, Track
from   view.plots.tasks     import TaskPlotCreator, CACHE_TYPE

from   ..computations       import extensions
from   ._model              import (QualityControlModelAccess,
                                    DriftControlPlotModel,
                                    DriftControlPlotTheme,
                                    DriftControlPlotConfig,
                                    ExtensionPlotTheme, ExtensionPlotConfig)

class DriftControlPlotCreator(TaskPlotCreator[QualityControlModelAccess,
                                              DriftControlPlotModel]):
    "Shows temperature temporal series"
    _theme:  DriftControlPlotTheme
    _config: DriftControlPlotConfig
    _src:    List[ColumnDataSource]
    _fig:    Figure
    def __init__(self, ctrl, mdl: QualityControlModelAccess, addto = True) -> None:
        super().__init__(ctrl, addto = False)
        name = "qc."+self.__class__.__name__.lower().replace("plotcreator", "")
        self._display.name   = name
        self._config .name   = name
        self._theme  .name   = name+".plot"
        self._theme  .ylabel = f'T {name[3:].lower()} (°C)'
        self._model          = mdl
        if addto:
            self.addto(ctrl, False)

    def _addtodoc(self, *_):
        "returns the figure"
        self._fig = self._theme.figure(y_range = Range1d(start = 0., end = 20.),
                                       x_range = Range1d(start = 0., end = 1e2),
                                       outline_line_width = self._theme.outlinewidth,
                                       outline_line_color = self._theme.outlinecolor,
                                       outline_line_alpha = 0.,
                                       name               = self.__class__.__name__)
        self._src = [ColumnDataSource(i) for i in self._data()]

        self.attrs(self._theme.measures).addto(self._fig, y = 'measures', x = 'cycles',
                                               source = self._src[0])
        for pop in ('pop10', 'median', 'pop90'):
            self.attrs(getattr(self._theme, pop)).addto(self._fig, x = 'cycles', y = pop,
                                                        source = self._src[1])

        self.fixreset(self._fig.x_range)
        self.fixreset(self._fig.y_range)
        return self._fig

    def _reset(self, cache:CACHE_TYPE):
        data = self._data()
        cache.update({i: dict(data = j) for i, j in zip(self._src, data)})

        self.setbounds(cache, self._fig.x_range, 'x',
                       (0., getattr(self._model.track, 'ncycles', 1)))

        xvals = data[0]['measures'][np.isfinite(data[0]['measures'])]
        xrng  = (np.min(xvals), np.max(xvals)) if len(xvals) else (0., 30.)
        self.setbounds(cache, self._fig.y_range, 'y', xrng)
        if len(xvals):
            perc, factor = self._config.yspan
            span         = np.percentile(xvals, perc)
            delta        = max(1e-5, span[1]-span[0])
            span         = span[0]-delta*factor, span[1]+delta*factor
            cache[self._fig.y_range].update(start = span[0], end = span[1])

        alpha = self._theme.outlinealpha if self._warn(data) else 0.
        cache[self._fig]['outline_line_alpha'] = alpha

    @staticmethod
    def reset(_):
        "make sure we never come here"
        raise AttributeError()

    @staticmethod
    def _defaults() -> Tuple[Dict[str, np.ndarray], ...]:
        empty = lambda: np.empty(0, dtype = 'f4')
        return (dict(measures = empty(), cycles = empty()),
                dict(cycles   = empty(),
                     pop10    = empty(),
                     median   = empty(),
                     pop90    = empty()))

    def _data(self) -> Tuple[Dict[str, np.ndarray], ...]:
        track = self._model.track
        if track is None:
            return self._defaults()

        cycles, meas  = self._measures(track)
        if meas is None or len(meas) == 0:
            return self._defaults()

        pops  = np.nanpercentile(meas, self._config.percentiles)
        return (dict(measures = meas, cycles = cycles),
                dict(cycles   = [np.nanmin(cycles), np.nanmax(cycles)],
                     pop10    = np.full(2, pops[0], dtype = 'f4'),
                     median   = np.full(2, pops[1], dtype = 'f4'),
                     pop90    = np.full(2, pops[2], dtype = 'f4')))

    @classmethod
    def _measures(cls, track: Track) -> Optional[np.ndarray]:
        name  = cls.__name__.replace('PlotCreator', '').lower()
        vals  = getattr(track.secondaries, name, None)
        if vals is None or not len(vals):
            return None, None

        length = np.nanmean(np.diff(track.phases[:,0]))
        return vals['index']/length, vals['value']

    def _warn(self, data):
        thr = self._config.warningthreshold
        return (False if thr is None or len(data[1]['pop10']) == 0 else
                (data[1]['pop90'][0] - data[1]['pop10'][0]) > thr)

class TSamplePlotCreator(DriftControlPlotCreator):
    "Shows TSample temperature temporal series"

class TSinkPlotCreator(DriftControlPlotCreator):
    "Shows TSink temperature temporal series"

class TServoPlotCreator(DriftControlPlotCreator):
    "Shows TServo temperature temporal series"

class ExtensionPlotCreator(DriftControlPlotCreator):
    "Shows bead extension temporal series"
    _theme: ExtensionPlotTheme
    def __init__(self, ctrl, mdl: QualityControlModelAccess) -> None:
        super().__init__(ctrl, mdl, False)
        self._plotmodel.theme  = ExtensionPlotTheme()
        self._plotmodel.config = ExtensionPlotConfig()
        self.addto(ctrl, False)

    def _addtodoc(self, *_):
        fig  = super()._addtodoc(_)
        args = dict(x = 'cycles', width  = self._theme.ybarswidth, source = self._src[-1])
        self.attrs(self._theme.ybars).addto(fig, top = 'top',    bottom = 'bottom', **args)
        self.attrs(self._theme.ymed) .addto(fig, top = 'median', bottom = 'median', **args)

        # set first of glyphs
        rends         = list(fig.renderers)
        fig.renderers = rends[:-6] + rends[-2:] + rends[-6:-2]
        return fig

    @classmethod
    def _defaults(cls) -> Tuple[Dict[str, np.ndarray], ...]:
        empty = lambda: np.empty(0, dtype = 'f4')
        data  = super()._defaults()
        return data + (dict(cycles = empty(),
                            median = empty(),
                            top    = empty(),
                            bottom = empty()),)

    def _data(self):
        data = super()._data()
        if len(data[0]['measures']) == 0:
            return data

        meas = data[0]['measures'].reshape((-1, self._model.track.ncycles)).T
        perc = list(self._config.ybarspercentiles) + [50]
        bars = np.nanpercentile(meas, perc, axis = 1)
        new  = dict(cycles = np.arange(bars.shape[1], dtype = 'i4'),
                    top    = bars[1,:],
                    median = bars[2,:],
                    bottom = bars[0,:])
        return data + (new,)

    def _measures(self, track: Track) -> Optional[np.ndarray]: # type: ignore
        beads = self._model.runbead()
        if beads is not None:
            cyc, cnt = extensions(cast(Beads, beads), *self._config.phases)
            return (np.concatenate(cyc), np.concatenate(cnt)) if len(cnt) else None
        return None

class QualityControlPlots:
    "All plots together"
    def __init__(self, ctrl, mdl):
        self.tsample = TSamplePlotCreator(ctrl, mdl)
        self.tsink   = TSinkPlotCreator(ctrl, mdl)
        self.tservo  = TServoPlotCreator(ctrl, mdl)
        self.ext     = ExtensionPlotCreator(ctrl, mdl)

    def observe(self, ctrl):
        "observe the controller"
        for i in self.__dict__.values():
            getattr(i, '_model').addto(ctrl, noerase = False)

    def reset(self, bkmodels):
        "resets the plots"
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', r'All-NaN slice encountered')
            for plot in self.__dict__.values():
                plot.delegatereset(bkmodels)

    def addtodoc(self, doc, mode):
        "returns the plot grid"
        plots   = [[getattr(i, '_addtodoc')(doc)] for i in self.__dict__.values()]
        for i in plots[1:]:
            i[0].x_range = plots[0][0].x_range
        for i in plots[:-1]:
            i[0].xaxis.visible = False

        tbar = getattr(self.tsample, '_theme').figargs()['toolbar_location']
        return layouts.gridplot(plots, **mode, toolbar_location = tbar)
