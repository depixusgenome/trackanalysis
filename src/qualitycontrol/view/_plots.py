#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Provides plots for temperatures and bead extensions"
import warnings
from   typing                import Dict, Union, Tuple, List, Any, cast

from   bokeh                 import layouts
from   bokeh.models          import (
    ColumnDataSource, Range1d, ToolbarBox, CustomAction, CustomJS, Div
)
from   bokeh.plotting        import Figure
import numpy                 as     np

from   data                  import Beads, Track
from   taskview.plots        import TaskPlotCreator, CACHE_TYPE

from   ..computations        import extensions
from   ._model               import (
    QualityControlModelAccess, DriftControlPlotModel, DriftControlPlotTheme,
    DriftControlPlotConfig, PlotDisplay, ExtensionPlotTheme, ExtensionPlotConfig
)

class DriftControlPlotCreator(TaskPlotCreator[QualityControlModelAccess,
                                              DriftControlPlotModel]):
    "Shows temperature temporal series"
    _plotmodel: DriftControlPlotModel
    _theme:     DriftControlPlotTheme
    _config:    DriftControlPlotConfig
    _src:       List[ColumnDataSource]
    _rends:     List[Tuple[str, Any]]
    _fig:       Figure
    def __init__(self, ctrl, **kwa) -> None:
        name         = "qc."+type(self).__name__.lower().replace("plotcreator", "")
        kwa.setdefault('config',  DriftControlPlotConfig()).name   = name
        kwa.setdefault('display', PlotDisplay())           .name   = name

        theme        = kwa.setdefault('theme',   DriftControlPlotTheme ())
        theme.name   = name+'.plot'
        theme.ylabel = f'T {name[3:].lower()} (°C)'
        super().__init__(ctrl, addto = True, noerase = False, **kwa)
        assert self._plotmodel.theme in ctrl.theme
        assert self._plotmodel.display in ctrl.display
        assert self._plotmodel.config in ctrl.theme

    def _addtodoc(self, ctrl, doc, *_): # pylint: disable=unused-argument
        "returns the figure"
        self._fig = self.figure(y_range = Range1d(start = 0., end = 20.),
                                x_range = Range1d(start = 0., end = 1e2),
                                outline_line_width = self._theme.outlinewidth,
                                outline_line_color = self._theme.outlinecolor,
                                outline_line_alpha = 0.,
                                name               = self.__class__.__name__)
        self._src = [ColumnDataSource(i) for i in self._data()]

        if self.__class__.__name__.startswith("T"):
            self._src[0].tags = ["csvtemperatures", self.__class__.__name__[:-len('PlotCreator')]]
        val = self.addtofig(self._fig, 'measures',
                            y = 'measures', x = 'cycles', source = self._src[0])
        self._rends = [('measures', val)]
        for pop in ('pop10', 'median', 'pop90'):
            val = self.addtofig(self._fig, pop, x = 'cycles', y = pop, source = self._src[1])
            self._rends.append((pop, val))
        return self._fig

    def _reset(self, cache:CACHE_TYPE):
        data = self._data()
        cache.update({i: dict(data = j) for i, j in zip(self._src, data)})

        yvals = data[0]['measures'][np.isfinite(data[0]['measures'])]
        self.setbounds(cache, self._fig,
                       [0., getattr(self._model.track, 'ncycles', 1)],
                       [np.min(yvals), np.max(yvals)] if len(yvals) else [0., 30.])

        if len(yvals):
            perc, factor = self._config.yspan
            span         = np.percentile(yvals, perc)
            delta        = max(1e-5, span[1]-span[0])
            span         = span[0]-delta*factor, span[1]+delta*factor
            cache[self._fig.y_range].update(start = span[0], end = span[1])

        alpha = self._theme.outlinealpha if self._warn(data) else 0.
        cache[self._fig]['outline_line_alpha'] = alpha
        self.setcolor(self._rends, cache = cache)

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
    def _measures(cls, track: Track
                 ) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[None, None]]:
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
    def __init__(self, ctrl, **kwa) -> None:
        super().__init__(ctrl,
                         theme  = ExtensionPlotTheme(),
                         config = ExtensionPlotConfig(), **kwa)

    def _addtodoc(self, ctrl, doc, *_):
        fig  = super()._addtodoc(ctrl, doc, *_)
        args = dict(x = 'cycles', width  = self._theme.ybarswidth, source = self._src[-1])
        val  = self.addtofig(fig, 'ybars', top = 'top',    bottom = 'bottom', **args)
        self._rends.append(('ybars', val))
        val  = self.addtofig(fig, 'ymed',  top = 'median', bottom = 'median', **args)
        self._rends.append(('ybars', val))

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

    def _measures(self, track: Track # type: ignore
                 ) -> Union[Tuple[np.ndarray, np.ndarray], Tuple[None, None]]:
        beads = self._model.runbead()
        if beads is not None:
            cyc, cnt = extensions(cast(Beads, beads), *self._config.phases)
            return ((np.concatenate(cyc), np.concatenate(cnt)) if len(cnt) else
                    (None, None))
        return None, None

    def _reset(self, cache:CACHE_TYPE):
        super()._reset(cache)
        if self._model.track:
            dim = self._model.track.instrument['dimension']
            lbl = self._theme.ylabel.split('(')[0]
            cache[self._fig.yaxis[0]].update(axis_label = f"{lbl} ({dim})")

class QualityControlPlots:
    "All plots together"
    def __init__(self, ctrl, mdl):
        self.tsample = TSamplePlotCreator(ctrl,   model = mdl)
        self.tsink   = TSinkPlotCreator(ctrl,     model = mdl)
        self.tservo  = TServoPlotCreator(ctrl,    model = mdl)
        self.ext     = ExtensionPlotCreator(ctrl, model = mdl)

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

    def addtodoc(self, ctrl, doc, mode):
        "returns the plot grid"
        plots   = [[getattr(i, '_addtodoc')(ctrl, doc)] for i in self.__dict__.values()]
        for i in plots[1:]:
            i[0].x_range = plots[0][0].x_range
        for i in plots[:-1]:
            i[-1].xaxis.visible = False
        css  = self.__add_csvaction(plots)

        tmp  = TSamplePlotCreator.fig(getattr(self.tsample, '_theme')).figargs()
        tbar = tmp['toolbar_location']
        grid = layouts.gridplot(plots, **mode, toolbar_location = tbar)
        # pylint: disable=not-an-iterable
        tbar = next(i for i in grid.children if isinstance(i, ToolbarBox))
        tbar.toolbar.logo = None
        return layouts.column(css, grid, **mode)

    @staticmethod
    def __add_csvaction(plots):
        srcs = sum((i[0].select(tags = 'csvtemperatures') for i in plots), [])
        plots[0][0].tools = plots[0][0].tools + [CustomAction(
            action_tooltip = "Save temperatures to CSV",
            callback       = CustomJS(
                code = """
                    var csvFile = 'cycle;value;sensor;\\n';
                    var ind     = 0;
                    for(ind = 0; ind < data.length; ++ind)
                    {
                        var sensor = ',"'+names[ind]+'"\\n';
                        var src    = data[ind].data;
                        var j      = 0;
                        var je     = src['cycles'].length;
                        for(j = 0; j < je; ++j)
                        {
                            csvFile += src["cycles"][j].toString()+',';
                            csvFile += src["measures"][j].toString()+sensor;
                        }
                    }

                    var blob = new Blob([csvFile], { type: 'text/csv;charset=utf-8;' });
                    if (navigator.msSaveBlob) { // IE 10+
                        navigator.msSaveBlob(blob, "temperatures.csv");
                    } else {
                        var link = document.createElement("a");
                        if (link.download !== undefined) { // feature detection
                            // Browsers that support HTML5 download attribute
                            var url = URL.createObjectURL(blob);
                            link.setAttribute("href", url);
                            link.setAttribute("download", "temperatures.csv");
                            link.style.visibility = 'hidden';
                            document.body.appendChild(link);
                            link.click();
                            document.body.removeChild(link);
                        }
                    }
                """,
                args = {'data':  srcs, 'names': [i.tags[1] for i in srcs]}
            )
        )]
        return Div(
            text   = "<link rel='stylesheet' type='text/css' href='view/qualitycontrol.css'>",
            width  = 0,
            height = 0
        )
