#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Provides plots for temperatures and bead extensions"
import warnings
from   typing               import Dict, Optional, Tuple, cast

from   bokeh                import layouts
from   bokeh.models         import ColumnDataSource, Range1d
from   bokeh.plotting       import Figure
import numpy                as     np

from   data                 import Beads, Track
from   view.plots.tasks     import TaskPlotCreator

from   ..computations       import extensions
from   ._model              import (QualityControlModelAccess,
                                    DriftControlPlotModel,
                                    DriftControlPlotTheme,
                                    DriftControlPlotConfig,
                                    ExtensionPlotTheme)

class DriftControlPlotCreator(TaskPlotCreator[QualityControlModelAccess,
                                              DriftControlPlotModel]):
    "Shows temperature temporal series"
    _theme:  DriftControlPlotTheme
    _config: DriftControlPlotConfig
    _fig:    Figure
    def __init__(self, ctrl, mdl: QualityControlModelAccess, **kwa) -> None:
        name = self.__class__.__name__.replace('PlotCreator', '')
        kwa.setdefault("ylabel", f'T {name[1:].lower()} (°C)')
        super().__init__(ctrl, name = name, **kwa)
        self._tasks                 = mdl
        self._src: ColumnDataSource = {}

    def _addtodoc(self, *_):
        "returns the figure"
        self._fig = self._theme.figure(y_range = Range1d(start = 0., end = 20.),
                                       x_range = Range1d(start = 0., end = 1e2),
                                       outline_line_width = self._theme.outlinewidth,
                                       outline_line_color = self._theme.outlinecolor,
                                       outline_line_alpha = 0.,
                                       name               = self.__class__.__name__)
        self._src = [ColumnDataSource(i) for i in self._data()]

        self._theme.measures.addto(self._fig, y = 'measures', x = 'cycles',
                                   source = self._src[0])
        for pop in ('pop10', 'median', 'pop90'):
            getattr(self._theme, pop).addto(self._fig, x = 'cycles', y = pop,
                                            source = self._src[1])

        self.fixreset(self._fig.x_range)
        self.fixreset(self._fig.y_range)
        return self._fig

    def _reset(self):
        data = self._data()
        for i, j in zip(self._src, data):
            self._bkmodels[i]['data'] = j

        self.setbounds(self._fig.x_range, 'x', (0., getattr(self._tasks.track, 'ncycles', 1)))

        xvals = data[0]['measures'][np.isfinite(data[0]['measures'])]
        xrng  = (np.min(xvals), np.max(xvals)) if len(xvals) else (0., 30.)
        self.setbounds(self._fig.y_range, 'y', xrng)
        if len(xvals):
            perc, factor = self._config.yspan
            span         = np.percentile(xvals, perc)
            delta        = max(1e-5, span[1]-span[0])
            span         = span[0]-delta*factor, span[1]+delta*factor
            self._bkmodels[self._fig.y_range].update(start = span[0], end = span[1])

        alpha = self._theme.outlinealpha if self._warn(data) else 0.
        self._bkmodels[self._fig]['outline_line_alpha'] = alpha

    @staticmethod
    def _defaults() -> Tuple[Dict[str, np.ndarray], ...]:
        empty = lambda: np.empty(0, dtype = 'f4')
        return (dict(measures = empty(), cycles = empty()),
                dict(cycles   = empty(),
                     pop10    = empty(),
                     median   = empty(),
                     pop90    = empty()))

    def _data(self) -> Tuple[Dict[str, np.ndarray], ...]:
        track = self._tasks.track
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
    def __init__(self, *args):
        super().__init__(*args)
        self._plotmodel.theme = ExtensionPlotTheme(ylabel = 'δ(Φ3-Φ1) (µm)')
        self._plotmodel.config.warningthreshold = 1.5e-2
        self._plotmodel.config.percentiles      = [25, 75]

    def _addtodoc(self, *_):
        fig  = super()._addtodoc(_)
        args = dict(x = 'cycles', width  = self._theme.ybarswidth, source = self._src[-1])
        self._theme.ybars.addto(fig, top = 'top',    bottom = 'bottom', **args)
        self._theme.ymed .addto(fig, top = 'median', bottom = 'median', **args)

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

        meas = data[0]['measures'].reshape((-1, self._tasks.track.ncycles)).T
        perc = list(self._config.percentiles) + [50]
        bars = np.nanpercentile(meas, perc, axis = 1)
        new  = dict(cycles = np.arange(bars.shape[1], dtype = 'i4'),
                    top    = bars[1,:],
                    median = bars[2,:],
                    bottom = bars[0,:])
        return data + (new,)

    def _measures(self, track: Track) -> Optional[np.ndarray]: # type: ignore
        beads = self._tasks.runbead()
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

    def observe(self, _):
        "sets up observers"
        for i in self.__dict__.values():
            i.observe(_)

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

        tbar = self.tsample.figargs()['toolbar_location']
        return layouts.gridplot(plots, **mode, toolbar_location = tbar)
