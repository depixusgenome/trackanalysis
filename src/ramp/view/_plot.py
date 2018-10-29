#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, Tuple, cast

from    bokeh.models   import ColumnDataSource, Range1d
from    bokeh.plotting import Figure
from    bokeh          import layouts

import  numpy                   as     np

from    data.views              import Beads
from    view.plots              import PlotView, CACHE_TYPE
from    view.plots.tasks        import TaskPlotCreator
from    control                 import Controller

from    ._model                 import (RampPlotModel, RampPlotTheme,
                                        RampPlotDisplay, RampTaskPlotModelAccess,
                                        observetracks)
from    ._widget                import WidgetMixin

_DATA_T = Tuple[Dict[str, np.ndarray], ...] # pylint: disable=invalid-name
class RampPlotCreator(TaskPlotCreator[RampTaskPlotModelAccess, RampPlotModel],
                      WidgetMixin):
    "Building the graph of cycles"
    _theme:         RampPlotTheme
    _display:       RampPlotDisplay
    _plotmodel:     RampPlotModel
    __src:          Tuple[ColumnDataSource,...]
    __fig:          Figure
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl, noerase = False)
        WidgetMixin.__init__(self, ctrl, self._plotmodel)

    def observe(self, ctrl):
        "sets-up model observers"
        super().observe(ctrl)
        self._widgetobservers(ctrl)
        observetracks(self._plotmodel, ctrl)

        @ctrl.display.observe(self._display)
        def _ondataframes(old = (), **_):
            if len({"dataframe", "consensus"} & set(old)):
                self.reset(False)

        @ctrl.theme.observe(self._theme)
        def _ondisplaytype(old = (), **_):
            if "dataformat" in old:
                self.reset(False)

    def _addtodoc(self, ctrl, *_):
        self.__src = [ColumnDataSource(data = i) for i in self.__data(None, None)]
        label      = (self._theme.ylabel if self._theme.dataformat != "norm" else
                      self._theme.ylabelnormalized)
        self.__fig = fig = self.figure(y_range      = Range1d,
                                       x_range      = Range1d,
                                       y_axis_label = label,
                                       name         = 'Ramp:Cycles')
        for i, j in zip(("beadarea", "beadline"), self.__src):
            self.addtofig(fig, i, x = 'zmag', y = 'zbead', source = j)
        for i, j in zip(("consensusarea", "consensusline", "beadcycles"), self.__src):
            self.addtofig(fig, i, x = 'zmag', y = 'z', source = j)
        self._display.addcallbacks(self._ctrl, fig)

        mode = self.defaultsizingmode(width = self._theme.widgetwidth)
        left = layouts.widgetbox(self._createwidget(ctrl), **mode)
        return self._keyedlayout(ctrl, fig, left = left)

    def _reset(self, cache: CACHE_TYPE):
        cycles, zmag, disable = None, None, True
        track                 = self._model.track
        try:
            if track is not None:
                view    = self._model.runbead()
                if view is not None:
                    cycles  = list(cast(Beads, view)[self._model.bead,...].values())
                    zmag    = list(track.secondaries.zmagcycles.values())
                    disable = False
        finally:
            data = self.__data(cycles, zmag)
            extr = lambda x: ([np.nanmin(i[x])  for i in data if len(i[x])]
                              +[np.nanmax(i[x]) for i in data if len(i[x])])

            self.setbounds(cache, self.__fig.x_range, 'x', extr("zmag"))
            self.setbounds(cache, self.__fig.y_range, 'y', extr("z"))

            label = (self._theme.ylabel if self._theme.dataformat != "norm" else
                     self._theme.ylabelnormalized)
            cache[self.__fig.yaxis[0]]["axis_label"] = label
            for i, j in zip(data, self.__src):
                cache[j]['data'] = i
            self._resetwidget(cache, disable)

    def __data(self, cycles, zmag) -> _DATA_T:
        empty            = np.empty(0, dtype = 'f4')
        outp: _DATA_T    = tuple({i: empty for i in ("z", "zmag", "zbead")}
                                 for j in range(3))
        outp[2].pop("zbead")
        if cycles is None or len(cycles) == 0:
            return outp

        conc = lambda x: np.concatenate(list(x))
        if self._theme.dataformat == "raw":
            get2 = lambda x: conc([np.NaN] if j else i for i in x for j in (0, 1))
            outp[2].update(z = get2(cycles), zmag  = get2(zmag))

        else:
            cons = self._plotmodel.getdisplay("consensus")
            if cons is not None:
                bead = self._model.bead
                if self._theme.dataformat == "norm":
                    name   = "normalized"
                    factor = 100. / np.nanmax(cons[bead, 1])
                else:
                    name   = "consensus"
                    factor = 1.

                get0 = lambda i, j, k: conc([cons[i, j], cons[i, k][::-1]])
                outp[0].update(z     = get0(name, 0, 2),
                               zmag  = get0("zmag", "", ""),
                               zbead = get0(bead, 0, 2)*factor)
                outp[1].update(z     = cons[name, 1],
                               zmag  = cons["zmag", ""],
                               zbead = cons[bead, 1]*factor)
        return outp

class RampView(PlotView[RampPlotCreator]):
    "Peaks plot view"
    TASKS = ('extremumalignment',)
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks = self.TASKS)
