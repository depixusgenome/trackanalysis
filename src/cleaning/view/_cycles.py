#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"

from    typing         import Dict, Sequence, Tuple, TYPE_CHECKING

from    bokeh.plotting import figure, Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, CustomJS, Range1d
from    bokeh.model    import LayoutDOM
import  bokeh.core.properties as props
import  bokeh.colors

import  numpy                   as     np
from    numpy.lib.index_tricks  import as_strided

from    view.plots              import PlotAttrs
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

from    ._model                 import CyclesModelAccess

class DpxCleaning(LayoutDOM):
    "This starts tests once flexx/browser window has finished loading"
    __implementation__ = "_cycles.coffee"
    framerate          = props.Float(30.)
    figure             = props.Instance(Figure)

class CyclesPlotCreator(TaskPlotCreator):
    "Building the graph of cycles"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        cnf = self.css.cycles
        cnf.points      .default  = PlotAttrs('color',  'circle', 1, alpha   = .5)
        cnf.colors.basic.defaults = dict(good = 'blue', bad = 'red', extent = 'orange')
        cnf.colors.dark .defaults = dict(good = 'gray', bad = 'red', extent = 'orange')
        self.css.figure.width.default  = 500
        self.__source = None # type: ColumnDataSource
        self.__client = None # type: DpxCleaning
        if TYPE_CHECKING:
            self._model = CyclesModelAccess(self._ctrl, '')

    def _create(self, doc):
        self.__source = ColumnDataSource(data = self.__data())

        fig           = figure(**self._figargs(y_range = Range1d, name = 'Clean:Cycles'))
        self.__client = DpxCleaning(figure = fig)
        doc.add_root(self.__client)

        self.css.cycles.points.addto(fig, x = 't', y = 'z', source = self.__source)
        fig.extra_x_ranges = {"time": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name = "time", axis_label = self.css.xtoplabel.get())
        fig.add_layout(axis, 'above')
        fig.x_range.callback = CustomJS.from_coffeescript('mdl.onchangebounds()',
                                                          dict(mdl = self.__client))
        self._addcallbacks(self.__client.figure)
        return self.__model.figure

    def _reset(self):
        self._bkmodels[self.__source]['data'] = self.__data()

    def __data(self) -> Dict[str, np.ndarray]:
        items = self.__cyclevalues()
        val   = self.__zvalue(items)
        res   = dict(t     = self.__time(val).ravel(),
                     z     = val.ravel(),
                     cycle = self.__cycle(items, val).ravel(),
                     color = self.__color(items, val).ravel())
        assert all(len(i) == val.size for  i in res.values())
        return res

    def __cyclevalues(self) -> Sequence[Tuple[Tuple[int,...], Sequence[np.ndarray]]]:
        cache = self._model.datacleaning.cache
        trk   = self._model.track
        if None in (cache, trk):
            return [((0,0), [])]

        proc  = self._model.alignment.processor
        beads = trk.cycles if proc is None else proc.apply(trk.beads, **proc.config())
        items = list(beads[self._model.bead, ...])
        if len(items) == 0 or not any(len(i) for _, i in items):
            return [((0,0), [])]
        return items

    @staticmethod
    def __zvalue(items) -> np.ndarray:
        size = max(len(i) for _, i in items)
        val  = np.full((len(items), size), np.NaN, dtype = 'f4')
        for i, (_, j) in zip(val, items):
            i[:len(j)] = j
        return val

    @staticmethod
    def __time(val) -> np.ndarray:
        tmp   = np.arange(val.size, dtype = 'i4')
        return as_strided(tmp, shape = val.shape, strides = (0, tmp.strides[0]))

    @staticmethod
    def __cycle(items, val) -> np.ndarray:
        tmp = np.array([i[-1] for i, _ in items], dtype = 'i4')
        return as_strided(tmp, shape = val.shape, strides = (tmp.strides[0], 0))

    def __color(self, items, val) -> np.ndarray:
        inds  = np.argsort([i[-1] for i, _ in items])
        cnf   = self.css.colors[self.css.theme.get()]
        hexes = {i: getattr(bokeh.colors, cnf[i].get()).to_hex()
                 for i in ('good', 'hfsigma', 'extent')}

        tmp   = np.full(len(items), hexes['good'], dtype = '<U7')
        cache = self._model.datacleaning.cache
        for name, value in () if cache is None else cache.items():
            tmp[inds[value.low ]] = hexes[name]
            tmp[inds[value.high]] = hexes[name]

        return as_strided(tmp, shape = val.shape, strides = (tmp.strides[0], 0))
