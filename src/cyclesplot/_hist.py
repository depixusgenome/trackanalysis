#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Building a projection of phase 5"

import  warnings
from    abc            import ABC
from    typing         import Any, Callable, TYPE_CHECKING

from    bokeh.plotting import Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, Range1d

import  numpy          as np

from    model.level    import PHASE
from    sequences.view import SequenceTicker, estimatebias
from    view.plots     import checksizes, CACHE_TYPE
from    ._bokehext     import DpxHoverModel
from    ._model        import CyclesModelAccess, CyclesPlotTheme

class HistMixin(ABC):
    "Building a projection of phase 5 onto the Z axis"
    _theme: CyclesPlotTheme
    _model: CyclesModelAccess
    _hover: DpxHoverModel
    _ctrl:  Any
    _histsource: ColumnDataSource
    _hist:       Figure
    def __init__(self, ctrl):
        "sets up this plotter's info"
        DpxHoverModel.init(ctrl)
        SequenceTicker.init(ctrl)

    @checksizes
    def __data(self, data, shape): # pylint: disable=too-many-locals
        bins  = np.array([-1, 1])
        zeros = np.zeros((1,), dtype = 'f4')
        items: Any = (zeros,) # type: ignore
        if shape != (1, 0):
            phase = PHASE.measure
            zvals = data['z'].reshape(shape)
            if self._model.eventdetection.task is None:
                track = self._model.track
                ind1  = track.phases[:,phase]  -track.phases[:,0]
                ind2  = track.phases[:,phase+1]-track.phases[:,0]
                items = [val[ix1:ix2] for ix1, ix2, val in zip(ind1, ind2, zvals)]
            else:
                items = zvals

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category = RuntimeWarning)
                rng = (np.nanmin([np.nanmin(i) for i in items]),
                       np.nanmax([np.nanmax(i) for i in items]))
            if all(np.isfinite(i) for i in rng):
                width = self._model.cycles.config.binwidth
                bins  = np.arange(rng[0]-width*.5, rng[1]+width*1.01, width, dtype = 'f4')
                if bins[-2] > rng[1]:
                    bins = bins[:-1]

                size  = len(bins)-1
                items = [np.bincount(np.digitize(i, bins), minlength = size+1)[1:][:size]
                         for i in items]
                zeros = np.zeros((len(bins)-1,), dtype = 'f4')
            else:
                items = (zeros,)

        threshold = self._model.cycles.config.minframes
        return dict(frames  = np.sum(items, axis = 0),
                    cycles  = np.sum([np.int32(i > threshold) for i in items], axis = 0),
                    left    = zeros,
                    bottom  = bins[:-1],
                    top     = bins[1:])

    def _createhist(self, doc, data, shape, yrng):
        self._hist = self.figure(x_axis_label     = self._theme.histxlabel,
                                 y_axis_location = None,
                                 x_range         = Range1d(0, 5e4),
                                 y_range         = yrng,
                                 tooltips        = None,
                                 name            = 'Cycles:Hist')

        hist             = self.__data(data, shape)
        self._histsource = ColumnDataSource(hist)
        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 100.)}


        self.addtofig(self._hist, 'histframes',
                      source = self._histsource,
                      bottom = "bottom", top   = "top",
                      left   = "left",   right = "frames")

        rend = self.addtofig(self._hist, 'histcycles',
                             source = self._histsource,
                             bottom = "bottom", top   = "top",
                             left   = "left",   right = "cycles",
                             x_range_name = "cycles")

        axis  = LinearAxis(x_range_name          = "cycles",
                           axis_label            = self._theme.histxtoplabel,
                           axis_label_text_color = rend.glyph.line_color)
        self._hist.add_layout(axis, 'above')

        self._ticker = SequenceTicker(self._ctrl, self._hist, self._model,
                                      self._model.cycles.theme.yrightlabel, "right")
        self._hover = DpxHoverModel.create(self._ctrl, doc, self._hist, self._model, 'cycles')
        self._hover.slaveaxes(self._hist, self._histsource)

    def _oncyclessequence(self, **_):
        if self.isactive():
            with self.resetting() as cache:
                self._ticker.reset(cache)
                self._hover.reset(cache, self._ctrl, self._model)


    def _histobservers(self, ctrl):
        ctrl.theme.observe('sequence', self._oncyclessequence)

    def _resethist(self, cache:CACHE_TYPE, data, shape):
        hist = self.__data(data, shape)

        self._ctrl.display.update(self._model.cycles.display,
                                  estimatedbias = estimatebias(hist['bottom'], hist['cycles']))
        self._hover.reset(cache, self._ctrl, self._model)
        self._ticker.reset(cache)

        cache[self._histsource]['data'] = hist
        cache[self._hist.y_range] = self.newbounds('y', data['z'])

    if TYPE_CHECKING:
        newbounds: Callable
