#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import Dict

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import Figure
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        Model, TapTool, CustomJS)

import numpy                    as     np

from view.base                  import enableOnTrack
from view.colors                import tohex
from view.plots                 import PlotView, CACHE_TYPE
from view.plots.tasks           import TaskPlotCreator
from sequences.view             import SequenceTicker, SequenceHoverMixin
from peakfinding.histogram      import interpolator

from ._model                    import PeaksPlotModelAccess, PeaksPlotModel
from ._widget                   import createwidgets
from ._io                       import setupio

class PeaksSequenceHover(Model, SequenceHoverMixin):
    "tooltip over peaks"
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

    def pyslaveaxes(self, fig, src, resets): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        yrng         = fig.y_range
        bases        = fig.extra_y_ranges['bases']
        resets[bases].update(start  = (yrng.start - self._model.bias)*self._model.stretch,
                             end    = (yrng.end   - self._model.bias)*self._model.stretch)

        zval = src["z"]
        ix1  = 0
        ix2  = len(zval)
        for i in range(ix2):
            if zval[i] < yrng.start:
                ix1 = i+1
                continue
            if zval[i] > yrng.end:
                ix2 = i
                break

        end = lambda x: (0. if len(zval) < 2 or ix1 >= ix2 else max(src[x][ix1:ix2])+1)
        resets[fig.extra_x_ranges['duration']].update(start = 0., end = end('duration'))
        resets[fig.x_range]                   .update(start = 0., end = end('count'))

    def jsslaveaxes(self, fig, src): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        fig.y_range.callback = CustomJS(code = "hvr.on_change_bounds(fig, src)",
                                        args = dict(fig = fig, src = src, hvr = self))

class PeaksPlotCreator(TaskPlotCreator[PeaksPlotModelAccess, PeaksPlotModel]):
    "Creates plots for peaks"
    _fig: Figure
    def __init__(self, ctrl):
        super().__init__(ctrl)
        self._src: Dict[str, ColumnDataSource] = {}
        self._widgets                          = createwidgets(ctrl, self._model)
        self._ticker                           = SequenceTicker()
        self._hover                            = PeaksSequenceHover()
        self._ticker.init(ctrl)
        self._hover.init(ctrl)

    @property
    def model(self):
        "returns the model"
        return self._model

    def __colors(self, name):
        return tohex(self._theme.colors[self.model.themename][name])

    def __peaks(self, vals = None):
        colors = [self.__colors(i) for i in ('found', 'missing', 'reference')]

        peaks  = dict(self._model.peaks)
        if vals is not None and self._model.identification.task is not None:
            alldist = self._model.distances
            for key in self._model.sequences(...):
                if key not in alldist:
                    continue
                peaks[key+'color'] = np.where(np.isfinite(peaks[key+'id']), *colors[:2])

            if self._model.sequencekey not in alldist and alldist:
                self._model.sequencekey = max(tuple(alldist),
                                              key = lambda x: alldist[x].value)
            peaks['color'] = peaks[self._model.sequencekey+'color']
        elif self._model.fittoreference.referencepeaks is not None:
            peaks['color'] = np.where(np.isfinite(peaks['id']), colors[2], colors[0])
        else:
            peaks['color'] = [colors[0]]*len(peaks['id'])
        return peaks

    def __defaults(self):
        empty = lambda *cols: {i: np.empty(0, dtype = 'f4') for i in cols}
        return {'':        empty('z', 'count', 'ref'),
                'events' : empty('z', 'count'),
                'peaks':   self.__peaks(None)}

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
        return self._keyedlayout(ctrl, self._fig, left = self.__setup_widgets(doc))

    def observe(self, ctrl):
        "observes the model"
        super().observe(ctrl)
        self._model.setobservers(ctrl)
        for widget in self._widgets.values():
            widget.observe(ctrl)

    def ismain(self, _):
        "specific setup for when this view is the main one"
        self._widgets['advanced'].ismain(_)

    def _reset(self, cache:CACHE_TYPE):
        dicos = None
        try:
            dicos = self.__data()
        finally:
            if dicos is None:
                dicos = self.__defaults()

            for i, j in dicos.items():
                cache[self._src[i]].update(data = j, column_names = list(j.keys()))

            self._hover .reset(cache)
            self._ticker.reset(cache)
            for widget in self._widgets.values():
                widget.reset(cache)

            data = dicos['']
            if len(data['z']) > 2:
                self.setbounds(cache, self._fig.y_range, 'y', (data['z'][0], data['z'][-1]))
            else:
                self.setbounds(cache, self._fig.y_range, 'y', (0., 1.))

    def __create_fig(self):
        self._fig = self._theme.figure(y_range = Range1d(start = 0., end = 1.),
                                       x_range = Range1d(start = 0., end = 1e3),
                                       name    = 'Peaks:fig')
        self._fig.extra_x_ranges = {"duration": Range1d(start = 0., end = 1.)}
        axis  = LinearAxis(x_range_name          = "duration",
                           axis_label            = self._theme.xtoplabel,
                           axis_label_text_color = self._theme.peaksduration.color
                          )
        self._fig.xaxis[0].axis_label_text_color = self._theme.peakscount.color
        self._fig.add_layout(axis, 'above')
        self._plotmodel.theme.addcallbacks(self._ctrl, self._fig)

    def __add_curves(self):
        self._src = {i: ColumnDataSource(j) for i, j in self.__data().items()}

        rends = []
        for key in ('reference.count', 'count', 'events.count',
                    'peaks.count', 'peaks.duration'):
            src  = self._src.get(key.split('.')[0], self._src[''])
            args = dict(x      = 'ref' if key.startswith('ref') else key.split('.')[-1],
                        y      = 'z',
                        source = src)
            if 'duration' in key:
                args['x_range_name'] = 'duration'

            if 'peaks' in key:
                args['line_color'] = 'color'
            val = getattr(self._theme, key.replace('.', '')).addto(self._fig, **args)
            if 'peaks' in key:
                rends.append(val)
        return rends

    def __setup_tools(self, doc, rends):
        tool = self._fig.select(TapTool)
        if len(tool) == 1:
            tool[0].renderers = rends[::-1]

        self._hover.create(self._fig, self._model, self)
        doc.add_root(self._hover)
        self._ticker.create(self._fig, self._model, self)
        self._hover.jsslaveaxes(self._fig, self._src['peaks'])

    def __setup_widgets(self, doc):
        action  = self.action
        wdg     = {i: j.addtodoc(action, self._src['peaks'])
                   for i, j in self._widgets.items()}
        enableOnTrack(self, self._fig, wdg)
        self._widgets['cstrpath'].listentofile(doc, action)


        self._widgets['advanced'].callbacks(self._doc)
        self._widgets['seq'].callbacks(self._hover,
                                       self._ticker,
                                       wdg['stats'][-1],
                                       wdg['peaks'][-1])

        mode     = self.defaultsizingmode()
        wbox     = lambda x: layouts.widgetbox(children = x, **mode)
        left     = sum((wdg[i] for i in ('ref', 'seq','oligos','cstrpath', 'advanced')), [])
        children = [[wbox(left), wbox(wdg['stats'])], [wbox(wdg['peaks'])]]
        return layouts.layout(children = children, **mode)

    def advanced(self):
        "triggers the advanced dialog"
        self._widgets['advanced'].on_click()

    def activate(self, val):
        "activates the component: resets can occur"
        self._widgets['cstrpath'].listentofile = val
        super().activate(val)

class PeaksPlotView(PlotView[PeaksPlotCreator]):
    "Peaks plot view"
    TASKS = 'extremumalignment', 'eventdetection', 'peakselector'
    def advanced(self):
        "triggers the advanced dialog"
        self._plotter.advanced()

    def ismain(self, ctrl):
        "Alignment, ... is set-up by default"
        self._ismain(ctrl, tasks = self.TASKS, **setupio(self._plotter.model))
