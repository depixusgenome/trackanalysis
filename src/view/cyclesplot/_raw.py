#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from    typing         import (Optional, Tuple, # pylint: disable=unused-import
                               TYPE_CHECKING)

from    bokeh.plotting import figure, Figure    # pylint: disable=unused-import
from    bokeh.models   import LinearAxis, ColumnDataSource, CustomJS, Range1d

import  numpy                   as     np
from    numpy.lib.index_tricks  import as_strided

from  ..plotutils           import PlotAttrs

class RawMixin:
    "Building the graph of cycles"
    def __init__(self):
        "sets up this plotter's info"
        self.css.defaults = dict(raw        = PlotAttrs('color',  'circle', 1,
                                                        alpha      = .5,
                                                        palette    = 'inferno'),
                                 plotwidth  = 500)
        self._rawsource = None # type: Optional[ColumnDataSource]
        self._raw       = None # type: Optional[Figure]

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

    def __data(self, cycles, bead) -> Tuple[dict, Tuple[int,int]]:
        if cycles is None:
            return (dict.fromkeys(('t', 'z', 'cycle', 'color'), [0., 1.]),
                    (1, 2))

        items = list(cycles)
        if len(items) == 0 or not any(len(i) for _, i in items):
            return self.__data(None, bead)

        if self._model.eventdetection.task is None:
            res, shape = self.__normal_data(items)
        else:
            res, shape = self.__event_data(items)

        tmp          = np.array([i[-1] for i, _ in items], dtype = 'i4')
        res['cycle'] = (as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))
                        .ravel())

        tmp          = np.array(self.css.raw.get().listpalette(shape[0]))
        res['color'] = (as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))
                        .ravel())

        assert all(len(i) == len(res['z']) for  i in res.values())
        return res, shape

    def __addcallbacks(self):
        fig = self._raw
        self._addcallbacks(fig)

        def _onchangebounds(frng = fig.x_range,
                            trng = fig.extra_x_ranges["time"],
                            mdl  = self._hover):
            # pylint: disable=protected-access,no-member
            if frng.bounds is not None:
                frng._initial_start = frng.bounds[0]
                frng._initial_end   = frng.bounds[1]
            trng.start = frng.start/mdl.framerate
            trng.end   = frng.end  /mdl.framerate
        fig.x_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createraw(self, track, bead):
        css             = self.css
        self._raw       = figure(y_axis_label = css.ylabel.get(),
                                 y_range      = Range1d(start = 0., end = 0.),
                                 name         = 'Cycles:Raw',
                                 **self._figargs(css))
        raw, shape      = self.__data(track, bead)
        self._rawsource = ColumnDataSource(data = raw)

        css.raw.addto(self._raw, x = 't', y = 'z', source = self._rawsource)

        self._hover.createraw(self._raw, self._rawsource, shape,
                              self._model, self.css)
        self._raw.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}

        axis = LinearAxis(x_range_name="time", axis_label = css.xtoplabel.get())
        self._raw.add_layout(axis, 'above')
        self.__addcallbacks()
        return shape

    def _updateraw(self, track, bead):
        data, shape          = self.__data(track, bead)
        self._rawsource.data = data
        self.setbounds(self._hist.y_range, 'y', data['z'])
        self._hover.updateraw(self._raw, self._rawsource, shape)
        return shape

    if TYPE_CHECKING:
        css       = None # type: ignore
        _model    = None # type: ignore
