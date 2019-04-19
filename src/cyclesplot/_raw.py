#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from    typing         import Tuple, Callable
from    abc            import ABC

from    bokeh.plotting import Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, CustomJS, Range1d

import  numpy                   as     np
from    numpy.lib.index_tricks  import as_strided

from    view.plots      import CACHE_TYPE
from    ._bokehext      import DpxHoverModel
from    ._model         import CyclesPlotTheme, CyclesModelAccess

class RawMixin(ABC):
    "Building the graph of cycles"
    _theme    : CyclesPlotTheme
    _model    : CyclesModelAccess
    _hover    : DpxHoverModel
    attrs     : Callable
    newbounds : Callable
    def __init__(self):
        "sets up this plotter's info"
        self._rawsource: ColumnDataSource = None
        self._raw:       Figure           = None

    @staticmethod
    def __normal_data(items):
        size = max(len(i) for _, i in items)
        val  = np.full((len(items), size), np.NaN, dtype = 'f4')
        for i, (_, j) in zip(val, items):
            i[:len(j)] = j

        tmp   = np.arange(size, dtype = 'i4')
        time  = as_strided(tmp, shape = val.shape, strides = (0, tmp.strides[0]))
        return dict(t = time.ravel(), z = val.ravel()), val.shape

    @staticmethod
    def __event_data(items):
        size = max(j[0]+len(j[1])+k for _, i in  items for k, j in enumerate(i))
        val  = np.full ((len(items), size), np.NaN, dtype = 'f4')
        time = np.full ((len(items), size), np.NaN, dtype = 'f4')

        for xvals, tvals, (_, j) in zip(val, time, items):
            for k, (start, arr) in enumerate(j):
                xvals[start+k:start+k+len(arr)] = arr
                tvals[start+k:start+k+len(arr)] = np.arange(start, start+len(arr))

        return dict(t = time.ravel(), z = val.ravel()), val.shape

    _DEFAULT_DATA = ({i: np.array([], dtype = 'f4') for i in ('t', 'z', 'cycle', 'color')},
                     (1, 0))

    def __data(self) -> Tuple[dict, Tuple[int,int]]:
        cycles = self._model.runbead()
        if cycles is None:
            return self._DEFAULT_DATA

        items = list(cycles)
        if len(items) == 0 or not any(len(i) for _, i in items):
            return self.__data()

        if self._model.eventdetection.task is None:
            res, shape = self.__normal_data(items)
        else:
            res, shape = self.__event_data(items)

        tmp          = np.array([i[-1] for i, _ in items], dtype = 'i4')
        res['cycle'] = (as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))
                        .ravel())

        tmp          = np.array(self.attrs(self._theme.raw)
                                .listpalette(shape[0], theme = self._model.themename))
        res['color'] = (as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))
                        .ravel())

        assert all(len(i) == len(res['z']) for  i in res.values())
        return res, shape

    def _finishraw(self, shape):
        fig = self._raw
        self._hover.createraw(self, fig, self._rawsource, shape, self._theme)
        self.linkmodeltoaxes(fig)
        fig.x_range.callback = CustomJS(code = "hvr.on_change_raw_bounds(cb_obj, trng)",
                                        args = dict(hvr  = self._hover,
                                                    trng = fig.extra_x_ranges["time"]))
        fcn = lambda attr, old, new: self._model.newparams(**{attr: new})
        self._hover.on_change("stretch", fcn)
        self._hover.on_change("bias",    fcn)

    def _createraw(self):
        self._raw = self.figure(
            y_range        = Range1d,
            tools          = self._theme.toolbar['raw'],
            name           = 'Cycles:Raw',
            extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        )
        self._raw.x_range.bounds = 'auto'
        raw, shape       = self._DEFAULT_DATA
        self._rawsource  = ColumnDataSource(data = raw)

        self.attrs(self._theme.raw).addto(self._raw, x = 't', y = 'z', source = self._rawsource)


        axis = LinearAxis(x_range_name="time", axis_label = self._theme.xtoplabel)
        self._raw.add_layout(axis, 'above')
        return shape

    def _resetraw(self, cache:CACHE_TYPE):
        data, shape = self._DEFAULT_DATA
        try:
            data, shape = self.__data()
        finally:
            cache[self._rawsource]['data'] = data
            self._hover.resetraw(self._raw, data, shape, cache)
            bnds                     = self.newbounds('x', data['t'])
            cache[self._raw.x_range] = {'bounds': (bnds['reset_start'], bnds['reset_end'])}

            if self._model.track:
                dim = self._model.track.instrument['dimension']
                lbl = self._theme.ylabel.split('(')[0]
                cache[self._raw.yaxis[0]].update(axis_label = f"{lbl} ({dim})")
        return shape
