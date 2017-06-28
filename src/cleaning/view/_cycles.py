#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from    typing         import (Optional, Tuple, # pylint: disable=unused-import
                               TYPE_CHECKING)

from    bokeh.plotting import figure, Figure    # pylint: disable=unused-import
from    bokeh.models   import LinearAxis, ColumnDataSource, CustomJS, Range1d
from    bokeh.model    import Model
import  bokeh.core.properties as props
import  bokeh.colors

import  numpy                   as     np
from    numpy.lib.index_tricks  import as_strided

from    view.plots              import PlotAttrs
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

class DpxCyclesPlot(Model):
    "This starts tests once flexx/browser window has finished loading"
    __implementation__ = "_cycles.coffee"
    framerate          = props.Float(30.)
    figure             = props.Instance(Figure)

class CyclesPlotCreator(TaskPlotCreator):
    "Building the graph of cycles"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self.css.cycles.defaults = dict(dark  = PlotAttrs('color',  'circle', 1,
                                                          alpha   = .5),
                                        basic = PlotAttrs('color',  'circle', 1,
                                                          alpha   = .5))
        self.css.figure.width.default  = 500
        self.css.cycles.color.defaults = dict(good = 'blue', hfsigma = 'red', extent = 'orange')
        self.__source = None # type: ColumnDataSource
        self.__client = None # type: DpxCyclesPlot

    @staticmethod
    def __normal_data(items):
        size = max(len(i) for _, i in items)
        val  = np.full((len(items), size), np.NaN, dtype = 'f4')
        for i, (_, j) in zip(val, items):
            i[:len(j)] = j

        tmp   = np.arange(size, dtype = 'i4')
        time  = as_strided(tmp, shape = val.shape, strides = (0, tmp.strides[0]))
        return dict(t = time.ravel(), z = val.ravel()), val.shape

    def __data(self) -> Tuple[dict, Tuple[int,int]]:
        cycles = self._model.runbead()
        items  = [] if cycles is None else list(cycles)

        if len(items) == 0 or not any(len(i) for _, i in items):
            return dict.fromkeys(('t', 'z', 'cycle', 'color'), [0., 1.])

        res, shape   = self.__normal_data(items)
        tmp          = np.array([i[-1] for i, _ in items], dtype = 'i4')
        res['cycle'] = (as_strided(tmp, shape = shape, strides = (tmp.strides[0], 0))
                        .ravel())

        color        = getattr(bokeh.colors, self.css.color.good.get()).to_hex()
        res['color'] = np.array([color]*len(res))
        assert all(len(i) == len(res['z']) for  i in res.values())
        return res

    def _create(self, doc):
        css = self.css
        raw = self.__data()
        self.__source = ColumnDataSource(data = raw)

        fig           = figure(**self._figargs(y_range = Range1d, name = 'Clean:Cycles'))
        self.__client = DpxCyclesPlot(figure = fig)
        doc.add_root(self.__client)

        css.cycles[css.theme.get()].addto(fig, x = 't', y = 'z', source = self.__source)
        fig.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name = "time", axis_label = css.xtoplabel.get())
        fig.add_layout(axis, 'above')
        fig.x_range.callback = CustomJS.from_coffeescript('mdl.onchangebounds()',
                                                          dict(mdl = self.__client))
        self._addcallbacks(self.__client.figure)
        return self.__model.figure

    def _reset(self):
        self._bkmodels[self.__source]['data'] = self.__data()
