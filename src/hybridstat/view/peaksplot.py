#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import Dict, List, Tuple

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import Figure
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        Model, TapTool, CustomJS)

import numpy                    as     np

from peakfinding.histogram      import interpolator
from sequences.modelaccess      import SequenceAnaIO
from sequences.view             import SequenceTicker, SequenceHoverMixin
from view.colors                import tohex
from view.plots                 import PlotView, CACHE_TYPE
from view.plots.base            import themed
from view.plots.ploterror       import PlotError
from view.plots.tasks           import TaskPlotCreator

from ._model                    import (PeaksPlotModelAccess, PeaksPlotTheme,
                                        PeaksPlotModel, createpeaks)
from ._widget                   import PeaksPlotWidgets
from ._io                       import setupio

class PeaksSequenceHover(Model, SequenceHoverMixin):
    "tooltip over peaks"
    _rends: List
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    updating  = props.String('')
    biases    = props.Dict(props.String, props.Float)
    stretches = props.Dict(props.String, props.Float)
    __implementation__ = SequenceHoverMixin.impl('PeaksSequenceHover',
                                                 ('stretches: [p.Any, {}], '
                                                  'biases:    [p.Any, {}],'),
                                                 __file__)


    def create(self, fig, *args, **kwa):   # pylint: disable=arguments-differ
        "Creates the hover tool for histograms"
        super().create(fig, *args, **kwa)
        jsc = CustomJS(args = {'fig': fig, 'source': self.source},
                       code = 'cb_obj.apply_update(fig, source)')
        self.js_on_change("updating", jsc)

    def reset(self, resets):                # pylint: disable=arguments-differ
        "Creates the hover tool for histograms"
        dist = self._model.distances
        super().reset(resets,
                      biases    = {i: j.bias    for i, j in dist.items()},
                      stretches = {i: j.stretch for i, j in dist.items()})

    def jsslaveaxes(self, fig, src): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        rng = fig.y_range
        rng.callback = CustomJS(code = "hvr.on_change_bounds(fig, src)",
                                args = dict(fig = fig, src = src, hvr = self))
        rng = fig.extra_y_ranges["bases"]
        rng.callback = CustomJS(code = "hvr.on_change_bases(fig)",
                                args = dict(fig = fig, hvr = self))

class PeaksPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, PeaksPlotModel]):
    "Creates plots for peaks"
    _rends:  List[Tuple]
    _fig:    Figure
    _theme:  PeaksPlotTheme
    _errors: PlotError
    def __init__(self, ctrl):
        super().__init__(ctrl, noerase = False)
        self._src: Dict[str, ColumnDataSource] = {}
        self._widgets                          = PeaksPlotWidgets(ctrl, self._model)
        self._ticker                           = SequenceTicker()
        self._hover                            = PeaksSequenceHover()
        self._ticker.init(ctrl)
        self._hover.init(ctrl)

    @property
    def model(self):
        "returns the model"
        return self._model

    def __colors(self, name):
        return tohex(themed(self, getattr(self._theme, name).color)
                     if hasattr(self._theme, name) else
                     themed(self, self._theme.pkcolors)[name])

    def __defaults(self):
        empty = lambda *cols: {i: np.empty(0, dtype = 'f4') for i in cols}
        return {'':        empty('z', 'count', 'ref'),
                'events' : empty('z', 'count'),
                'peaks':   self.__peaks(None)}

    def __peaks(self, val):
        return createpeaks(self._model, self._theme.pkcolors, val)

    def __data(self) -> Dict[str, dict]:
        dtl = self._model.runbead()
        if dtl is None:
            return self.__defaults()

        fit2ref = self._model.fittoreference
        zvals   = dtl.binwidth*np.arange(len(dtl.histogram), dtype = 'f4')+dtl.minvalue

        data    = dict(z     = zvals,
                       count = dtl.histogram,
                       ref   = fit2ref.refhistogram(zvals))

        pos     = np.concatenate(dtl.positions)
        events  = dict(z     = pos,
                       count = interpolator(data['z'], data['count'], fit2ref.hmin)(pos))
        return {'': data, 'events': events, 'peaks': self.__peaks(dtl)}

    def _addtodoc(self, ctrl, doc):
        "returns the figure"
        self.__create_fig()
        rends = self.__add_curves()
        self.__setup_tools(doc, rends)

        self._widgets.advanced.observefigsize(ctrl, self._theme, doc, self._fig)
        return self._keyedlayout(ctrl, self._fig,
                                 left = self.__setup_widgets(ctrl, doc))

    def observe(self, ctrl):
        "observes the model"
        super().observe(ctrl)
        self._model.setobservers(ctrl)
        self._widgets.observe(ctrl)
        SequenceAnaIO.observe(ctrl)

    def ismain(self, _):
        "specific setup for when this view is the main one"
        self._widgets.advanced.ismain(_)

    def _reset(self, cache:CACHE_TYPE):
        def _color(name, axname, attr):
            clr  = self.__colors(name)
            axis = next(i for i in getattr(self._fig, attr)
                        if getattr(i, 'x_range_name', '') == axname)
            cache[axis].update(axis_label_text_color = clr)

        def _reset(tmp):
            dicos = self.__defaults() if tmp is None else tmp
            if (tmp is not None
                    and self._model.identification.task is not None
                    and len(self._model.distances) == 0):
                self._errors.reset(cache, "Fit unsuccessful!", False)

            for i, j in dicos.items(): # type: ignore
                cache[self._src[i]].update(data = j)

            self._hover .reset(cache)
            self._ticker.reset(cache)
            self._widgets.reset(cache, tmp is None)

            inds = dicos['']['z'][[0,-1]] if len(dicos['']['z']) > 2 else (0., 1.)
            self.setbounds(cache, self._fig.y_range, 'y', inds)

            _color('peakscount',    'default',  'below')
            _color('peaksduration', 'duration', 'above')

            for key, rend in self._rends:
                args = {'color': self.__colors(key)}
                if 'peaks' in key:
                    args['line_color'] = 'color'
                attrs = self.attrs(getattr(self._theme, key))
                attrs.setcolor(rend, cache = cache, **args)

        self._errors(cache, self.__data, _reset)

    def __create_fig(self):
        self._fig    = self.figure(y_range = Range1d(start = 0., end = 1.),
                                   x_range = Range1d(start = 0., end = 1e3),
                                   name    = 'Peaks:fig')
        self._fig.extra_x_ranges = {"duration": Range1d(start = 0., end = 1.)}
        axis  = LinearAxis(x_range_name          = "duration",
                           axis_label            = self._theme.xtoplabel,
                           axis_label_text_color = self.__colors('peaksduration')
                          )
        self._fig.xaxis[0].axis_label_text_color = self.__colors('peakscount')
        self._fig.add_layout(axis, 'above')
        self._plotmodel.display.addcallbacks(self._ctrl, self._fig)
        self._errors = PlotError(self._fig, self._theme)

    def __add_curves(self):
        self._src   = {i: ColumnDataSource(j) for i, j in self.__data().items()}

        self._rends = []
        rends       = []
        for key in ('reference.count', 'count', 'events.count',
                    'peaks.count', 'peaks.duration'):
            src  = self._src.get(key.split('.')[0], self._src[''])
            args = dict(x      = 'ref' if key.startswith('ref') else key.split('.')[-1],
                        y      = 'z',
                        source = src)
            if 'duration' in key:
                args['x_range_name'] = 'duration'

            key = key.replace('.', '')
            if 'peaks' in key:
                args['line_color'] = 'color'

            args['color'] = self.__colors(key)
            val = self.addtofig(self._fig, key, **args)
            if 'peaks' in key:
                rends.append(val)
            self._rends.append((key, val))
        return rends

    def __setup_tools(self, doc, rends):
        tool = self._fig.select(TapTool)
        if len(tool) == 1:
            tool[0].renderers = rends[::-1]

        self._hover.create(self._fig, self._model)
        doc.add_root(self._hover)
        self._ticker.create(self._ctrl, self._fig, self._model,
                            self._model.peaksmodel.theme.yrightlabel, "right")
        self._hover.jsslaveaxes(self._fig, self._src['peaks'])

    def __setup_widgets(self, ctrl, doc):
        wdg, enabler = self._widgets.addtodoc(self, ctrl, doc)
        enabler.extend(self._fig)

        mode     = self.defaultsizingmode()
        wbox     = lambda x: layouts.widgetbox(children = x, **mode)
        order    = 'ref', 'seq', 'fitparams', 'oligos','cstrpath', 'advanced'
        children = [[wbox(sum((wdg[i] for i in order), [])), wbox(wdg['stats'])],
                    [wbox(wdg['peaks'])]]
        return layouts.layout(children = children, **mode)

    def advanced(self):
        "triggers the advanced dialog"
        self._widgets.advanced.on_click()

    def activate(self, val):
        "activates the component: resets can occur"
        self._widgets.cstrpath.listentofile = val
        super().activate(val)

class PeaksPlotView(PlotView[PeaksPlotCreator]):
    "Peaks plot view"
    TASKS = 'extremumalignment', 'eventdetection', 'peakselector', 'singlestrand'
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self, ctrl):
        "Alignment, ... is set-up by default"
        self._ismain(ctrl, tasks = self.TASKS, **setupio(self._plotter.model))
