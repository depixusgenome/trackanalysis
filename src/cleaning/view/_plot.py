#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    functools                   import partial
from    typing                      import Dict, Optional
from    bokeh.plotting              import Figure
from    bokeh.models                import LinearAxis, ColumnDataSource, Range1d
from    bokeh                       import layouts

import  numpy                       as     np

from    taskmodel                   import PHASE, Task
from    utils.array                 import repeat
from    utils.logconfig             import getLogger
from    view.colors                 import tohex
from    taskview.plots              import (
    PlotError, PlotView, DpxHoverTool, CACHE_TYPE, TaskPlotCreator
)

from    eventdetection.processor    import ExtremumAlignmentProcessor
from    ._model                     import (DataCleaningModelAccess, CleaningPlotModel,
                                            CleaningPlotTheme)
from    ._widget                    import WidgetMixin
from    ..datacleaning              import DataCleaning, Partial
from    ..processor                 import (DataCleaningProcessor,
                                            ClippingProcessor, ClippingTask)
LOGS = getLogger(__name__)

class GuiExtremumAlignmentProcessor(ExtremumAlignmentProcessor):
    "gui processor for alignment"
    @classmethod
    def _cache_action(cls, cache, kwa, frame, info):
        bias, args = getattr(cls, '_bias_'+cls._get(kwa, 'phase').name)(kwa, frame, info)
        cache['alignment'] = Partial(
            "alignment",
            np.empty(0, dtype = 'i4'),
            np.nonzero(np.isnan(bias))[0],
            bias - np.nanmedian(bias),
        )

        return args.cycles.translate(False, bias)

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        if toframe is None:
            return partial(cls.apply, **cnf)
        cache = cnf.pop('cache')
        return toframe.withaction(partial(cls._cache_action, cache, cnf))

    def run(self, args):
        "updates the frames"
        cache = args.data.setcachedefault(self, dict())
        return args.apply(partial(self.apply, cache = cache, **self.config()))

class GuiClippingProcessor(ClippingProcessor):
    "gui processor clipping"
    @classmethod
    def _cache_action(cls, cache, task, frame, info):
        cpy = np.copy(info[1])
        raw = np.copy(cpy)
        task(frame.track, info[0], cpy)
        if task.minpopulation > 0.:
            cache['exc'] = cls.test(task, frame, (info[0], cpy))
        cache['gui'] = np.isnan(cpy)
        if np.any(cache['gui']):
            cache['clipping'] = task.partial(frame.track, info[0], raw)
            cache['clipping'].values[cache['clipping'].values == 0.] = np.NaN

        pha           = frame.track.phase.select(..., [PHASE.measure, PHASE.measure+1]).ravel()
        cache['discarded'] = Partial(
            "discarded",
            np.empty(0, dtype = 'i4'),
            np.empty(0, dtype = 'i4'),
            np.array([i.sum()/len(i) for i in np.split(np.isnan(cpy), pha)[1::2]], dtype = "f4")
        )
        cache['discarded'].values[cache['discarded'].values == 0.] = np.NaN
        return info

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a method that will"
        if toframe is None:
            return partial(cls.apply, **cnf)
        cache = cnf.pop('cache')
        return toframe.withaction(partial(cls._cache_action, cache, ClippingTask(**cnf)))

    def run(self, args):
        "updates the frames"
        cache = args.data.setcachedefault(self, dict())
        return args.apply(partial(self.apply, cache = cache, **self.config()))

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        curr = np.copy(info[1])
        exc  = super().compute(frame, (info[0], curr), cache = cache, **cnf)
        DataCleaning(**cnf).aberrant(info[1], clip = True)
        cache['gui'] = np.isnan(curr)
        cache['exc'] = exc

    @staticmethod
    def nans(mdl, nans):
        "returns an array with nan positions per cycle"
        if nans is None:
            return ()
        return (np.asarray(i, dtype = 'bool')
                for i in mdl.track.cycles.withdata({0:nans}).values())

    @classmethod
    def runbead(cls, mdl, **kwa):
        "updates the cache in the gui and returns the nans"
        ctx   = mdl.runcontext(cls, GuiExtremumAlignmentProcessor, GuiClippingProcessor, **kwa)
        items = exc = None
        nans: Dict[str, np.ndarray]  = {}
        with ctx as cycles:
            if cycles is not None:
                items = list(cycles[mdl.bead, ...])

                for name, tsk in (('aberrant', mdl.cleaning.task), ('clipping', mdl.clipping.task)):
                    if tsk:
                        exc        = ctx.taskcache(tsk).pop('exc', None) if exc is None else exc
                        nans[name] = ctx.taskcache(tsk).pop('gui', None)

                if mdl.cleaning.task is not None:
                    cls.__add(ctx, mdl, mdl.alignment.task, "alignment")
                    cls.__add(ctx, mdl, mdl.clipping.task,  "clipping")
                    cls.__add(ctx, mdl, mdl.clipping.task,  "discarded")

        return items, nans, exc

    @classmethod
    def __add(cls, ctx, mdl, tsk: Optional[Task], name: str):
        if tsk is None:
            clipping = Partial(
                name,
                np.empty(0, dtype = 'i4'),
                np.empty(0, dtype = 'i4'),
                np.zeros(mdl.track.ncycles, dtype = 'f4')
            )
        else:
            clipping = ctx.taskcache(tsk).pop(name, None)

        if clipping:
            val           = ctx.taskcache(mdl.cleaning.task)
            val[mdl.bead] = (val[mdl.bead][0]+(clipping,), val[mdl.bead][1])

class CleaningPlotCreator(TaskPlotCreator[DataCleaningModelAccess, CleaningPlotModel],
                          WidgetMixin):
    "Building the graph of cycles"
    _model:   DataCleaningModelAccess
    _theme:   CleaningPlotTheme
    _errors:  PlotError
    __source: ColumnDataSource
    __fig:    Figure
    def __init__(self,  ctrl) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl, noerase = False)
        WidgetMixin.__init__(self, ctrl, self._model)

    def _addtodoc(self, ctrl, doc, *_):
        self.__source = ColumnDataSource(data = self.__data(None, None))

        self.__fig = fig = self.figure(
            y_range        = Range1d,
            x_range        = Range1d,
            name           = 'Clean:Cycles',
            extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        )
        self.addtofig(fig, 'lines', x = 't', y = 'z', source = self.__source)
        glyph = self.addtofig(fig, 'points', x = 't', y = 'z', source = self.__source)
        hover = fig.select(DpxHoverTool)
        if hover:
            hover[0].tooltips  = self._theme.tooltips
            hover[0].renderers = [glyph]

        axis = LinearAxis(x_range_name = "time", axis_label = self._theme.xtoplabel)
        fig.add_layout(axis, 'above')

        self._errors = PlotError(self.__fig, self._theme)

        self.linkmodeltoaxes(fig)

        mode    = self.defaultsizingmode(width = self._theme.widgetwidth)
        widgets = self._createwidget(ctrl, doc, fig)
        order   = 'cleaning', 'align', 'advanced', 'table', 'sampling'
        left    = layouts.widgetbox(sum((widgets[i] for i in order), []), **mode)
        return self._keyedlayout(ctrl, fig, left = left)

    def _reset(self, cache: CACHE_TYPE):
        items   = nans = exc = None
        disable = True
        try:
            items, nans, exc = GuiDataCleaningProcessor.runbead(self._model)
            disable          = False
        except Exception as err: # pylint: disable=broad-except
            LOGS.exception(err)
            self._errors.reset(cache, err)
        else:
            self._errors.reset(cache, exc)
        finally:
            data        = self.__data(items, nans)
            self.setbounds(cache, self.__fig, data['t'], data['z'])
            cache[self.__source]['data'] = data

            if self._model.track:
                dim = self._model.track.instrument['dimension']
                lbl = self._theme.ylabel.split('(')[0]
                cache[self.__fig.yaxis[0]].update(axis_label = f"{lbl} ({dim})")

            self._resetwidget(cache, disable)

    def __data(self, items, nans) -> Dict[str, np.ndarray]:
        if items is None or len(items) == 0 or not any(len(i) for _, i in items):
            return {i: [] for i in ("t", "z", "cycle", "color")}

        dsampl = self._ctrl.theme.get('cleaning.downsampling', 'value', 0)
        order  = self._model.cleaning.sorted(self._theme.order)
        if dsampl > 1:
            size = (max(len(i) for _, i in items)//dsampl+1)*dsampl+1
        else:
            size = max(len(i) for _, i in items)+1
        val    = np.full((len(items), size), np.NaN, dtype = 'f4')
        for (_, i), j in items:
            val[order[i],:len(j)] = j

        res = dict(t     = repeat(range(val.shape[1]), val.shape[0], 0),
                   z     = val.ravel(),
                   cycle = repeat([i[-1] for i, _ in items], val.shape[1], 1),
                   color = self.__color(order, nans, val))
        assert all(len(i) == val.size for  i in res.values())

        if dsampl > 1:
            inds  = np.random.randint(0, dsampl, (val.shape[0], (size-1)//dsampl+1))
            inds += (np.arange(inds.shape[1])*dsampl).T
            inds[:,-1:] = size-1
            inds += (np.arange(inds.shape[0])*size)[None].T
            inds  = inds.ravel()
            res   = {i: j[inds] for i, j in res.items()}
        return res

    def __color(self, order, nancache, items) -> np.ndarray:
        hexes  = tohex(self._theme.colors)
        tmp    = np.full(items.shape, hexes['good'], dtype = '<U7')
        cache  = self._model.cleaning.cache
        for name in self._theme.order:
            if name in nancache:
                color   = hexes[name]
                cycnans = GuiDataCleaningProcessor.nans(self._model, nancache[name])
                for cyc, nans in enumerate(cycnans):
                    tmp[order[cyc],:len(nans)][nans] = color

            elif cache is not None:
                value, color = cache.get(name, None), hexes[name]
                if value is None:
                    continue

                if name == 'saturation':
                    tmp[order[self._model.cleaning.saturatedcycles(cache)]] = color
                else:
                    tmp[order[value.min]] = color
                    tmp[order[value.max]] = color

        return tmp.ravel()

    def observe(self, ctrl, noerase = True):
        "sets-up model observers"
        super().observe(ctrl, noerase)
        self._widgetobservers(ctrl)

class CleaningView(PlotView[CleaningPlotCreator]):
    "Peaks plot view"
    TASKS = 'aberrant', 'datacleaning', 'extremumalignment'
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks  = self.TASKS)
