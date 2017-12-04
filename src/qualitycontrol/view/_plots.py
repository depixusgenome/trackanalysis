#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Provides plots for temperatures and bead extensions"
from    typing              import Dict, Optional, Tuple
import  warnings
import  numpy               as     np

from    bokeh.models        import ColumnDataSource, Range1d
from    bokeh.plotting      import Figure, figure
from    bokeh               import layouts

from    data                import Cycles
from    model.level         import PHASE
from    view.plots          import PlotAttrs
from    view.plots.tasks    import TaskPlotCreator
from    cleaning.processor  import DataCleaningException
from    ._model             import QualityControlModelAccess

class DriftControlPlotCreator(TaskPlotCreator[QualityControlModelAccess]):
    "Shows temperature temporal series"
    def __init__(self, ctrl, mdl):
        super().__init__(ctrl)
        self._model       = mdl
        self.css.defaults = {'measures'     : PlotAttrs('lightblue', 'line', 2, alpha = .75),
                             'median'       : PlotAttrs('lightgreen', 'line', 2,
                                                        line_dash = 'dashed'),
                             'pop10'        : PlotAttrs('lightgreen', 'line', 2,
                                                        line_dash = [4]),
                             'pop90'        : PlotAttrs('lightgreen', 'line', 2,
                                                        line_dash = [4]),
                             'figure.width' : 700,
                             'figure.height': 150,
                             'ylabel'       : self._xlabel(),
                             'xlabel'       : 'Cycles'}

        self.config.tools.default             = 'pan,box_zoom,reset,save'
        self.config.lines.percentiles.default = [10, 50, 90]
        self.config.yspan.default             = [1, 99], 0.05
        self._src: ColumnDataSource           = {}
        self._fig: Figure                     = None

    def _create(self, _):
        "returns the figure"
        self._fig = figure(**self._figargs(y_range = Range1d(start = 0., end = 20.),
                                           x_range = Range1d(start = 0., end = 1e2),
                                           name    = self.__class__.__name__))
        self._src = [ColumnDataSource(i) for i in self._data()]

        self.css.measures.addto(self._fig, y = 'measures', x = 'cycles', source = self._src[0])
        for pop in ('pop10', 'median', 'pop90'):
            self.css[pop].addto(self._fig, x = 'cycles', y = pop, source = self._src[1])

        self.fixreset(self._fig.x_range)
        self.fixreset(self._fig.y_range)
        return self._fig

    def _reset(self):
        data = self._data()
        for i, j in zip(self._src, data):
            self._bkmodels[i]['data'] = j

        self.setbounds(self._fig.x_range, 'x', (0., getattr(self._model.track, 'ncycles', 1)))

        xvals = data[0]['measures'][np.isfinite(data[0]['measures'])]
        xrng  = (np.min(xvals), np.max(xvals)) if len(xvals) else (0., 30.)
        self.setbounds(self._fig.y_range, 'y', xrng)

        if len(xrng):
            perc, factor = self.config.yspan.get()
            span         = np.percentile(xvals, perc)
            span         = (span[0]-(span[1]-span[0])*factor,
                            span[1]+(span[1]-span[0])*factor)
            self._bkmodels[self._fig.y_range].update(start = span[0], end = span[1])

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

        pops  = np.nanpercentile(meas, self.config.lines.percentiles.get())
        return (dict(measures = meas, cycles = cycles),
                dict(cycles   = [np.nanmin(cycles), np.nanmax(cycles)],
                     pop10    = np.full(2, pops[0], dtype = 'f4'),
                     median   = np.full(2, pops[1], dtype = 'f4'),
                     pop90    = np.full(2, pops[2], dtype = 'f4')))

    @classmethod
    def _measures(cls, track) -> Optional[np.ndarray]:
        name  = cls.__name__.replace('PlotCreator', '').lower()
        vals  = getattr(track.secondaries, name, None)
        if vals is None or not len(vals):
            return None

        length = np.nanmean(np.diff(track.phases[:,0]))
        return vals['index']/length, vals['value']

    @classmethod
    def _xlabel(cls) -> str:
        name = cls.__name__.replace('PlotCreator', '')
        return f'T {name[1:].lower()} (°C)'

class TSamplePlotCreator(DriftControlPlotCreator):
    "Shows TSample temperature temporal series"

class TSinkPlotCreator(DriftControlPlotCreator):
    "Shows TSink temperature temporal series"

class TServoPlotCreator(DriftControlPlotCreator):
    "Shows TServo temperature temporal series"

class ExtensionPlotCreator(DriftControlPlotCreator):
    "Shows bead extension temporal series"
    def __init__(self, *args):
        super().__init__(*args)
        self.css.measures.default    = PlotAttrs('lightblue', 'circle', 1, alpha = .75)
        self.css.ybars.default       = PlotAttrs('lightblue', 'vbar', 1, alpha = .75)
        self.css.ymed.default        = PlotAttrs('lightblue', 'vbar', 1, fill_alpha = 0.)
        self.css.ybars.width.default = .8
        self.config.ybars.percentiles.default = [25, 75]

    def _create(self, _):
        fig  = super()._create(_)
        args = dict(x = 'cycles', width  = self.css.ybars.width.get(), source = self._src[-1])
        self.css.ybars.addto(fig, top = 'top',    bottom = 'bottom', **args)
        self.css.ymed .addto(fig, top = 'median', bottom = 'median', **args)

        # set first of glyphs
        rends         = list(fig.renderers)
        fig.renderers = rends[:-6] + rends[-2:] + rends[-5:-2]
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
        perc = list(self.config.ybars.percentiles.get()) + [50]
        bars = np.nanpercentile(meas, perc, axis = 1)
        new  = dict(cycles = np.arange(bars.shape[1], dtype = 'i4'),
                    top    = bars[1,:],
                    median = bars[2,:],
                    bottom = bars[0,:])
        return data + (new,)

    def _measures(self, track) -> Optional[np.ndarray]: # type: ignore
        beads = self._model.runbead()
        if beads is None:
            return None

        cycles = Cycles(track = track).withaction(lambda _, i: (i[0], np.nanmedian(i[1])))
        dtype  = np.dtype('i4, f4')

        cnt    = []
        cyc    = []
        for ibead in beads.keys():
            try:
                data = beads[ibead]
            except DataCleaningException:
                continue

            ext = np.full(track.ncycles, np.NaN, dtype = 'f4')
            cnt.append(ext)
            cyc.append(np.arange(len(ext)))

            cycles.withdata({0: data}).withphases(PHASE.initial)
            tmp             = np.array([(i[1], j) for i, j in cycles], dtype = dtype)
            ext[tmp['f0']]  = tmp['f1']

            cycles.withphases(PHASE.pull)
            tmp             = np.array([(i[1], j) for i, j in cycles], dtype = dtype)
            ext[tmp['f0']] -= tmp['f1']

            ext[:]         -= np.nanmedian(ext)

        return (np.concatenate(cyc), np.concatenate(cnt)) if len(cnt) else None

    @staticmethod
    def _xlabel() -> str:
        return 'δ(Φ3-Φ1) (µm)'

class QualityControlPlots:
    "All plots together"
    def __init__(self, ctrl, mdl):
        self.tsample = TSamplePlotCreator(ctrl, mdl)
        self.tsink   = TSinkPlotCreator(ctrl, mdl)
        self.tservo  = TServoPlotCreator(ctrl, mdl)
        self.ext     = ExtensionPlotCreator(ctrl, mdl)

    def observe(self):
        "observations are delegated to the main PlotCreator"

    def reset(self, bkmodels):
        "resets the plots"
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', r'All-NaN slice encountered')
            for plot in self.__dict__.values():
                plot.delegatereset(bkmodels)

    def create(self, doc, mode):
        "returns the plot grid"
        plots   = [[getattr(getattr(self, i), '_create')(doc)]
                   for i in ('ext', 'tsample', 'tsink', 'tservo')]
        for i in plots[1:]:
            i[0].x_range = plots[0][0].x_range
        for i in plots[:-1]:
            i[0].xaxis.visible = False

        tbar = self.tsample.css.toolbar_location.get()
        return layouts.gridplot(plots, **mode, toolbar_location = tbar)
