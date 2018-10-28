#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, Tuple, cast

from    bokeh.models   import ColumnDataSource, Range1d
from    bokeh.layouts  import column
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

        def _ondataframes(old = (), **_):
            if len({"dataframe", "consensus"} & set(old)) and self.isactive():
                self.reset(False)
        ctrl.display.observe(self._display, _ondataframes)

    def _addtodoc(self, ctrl, *_):
        self.__src = [ColumnDataSource(data = i) for i in self.__data(None, None)]
        label      = (self._theme.ylabel if not self._config.consensus.normalize else
                      self._theme.ylabelnormalized)
        self.__fig = fig = self.figure(y_range      = Range1d,
                                       x_range      = Range1d,
                                       y_axis_label = label,
                                       name         = 'Ramp:Cycles')
        for i, j in zip(("beadarea", "beadline"), self.__src):
            self.addtofig(fig, i, x = 'zmag', y = 'zbead', source = j)
        for i, j in zip(("consensusarea", "consensusline", "beadcycles"), self.__src):
            self.addtofig(fig, i, x = 'zmag', y = 'z', source = j)
        self.fixreset(fig.y_range)
        self._display.addcallbacks(self._ctrl, fig)

        mode    = self.defaultsizingmode(width = self._theme.widgetwidth)
        widgets = self._createwidget(ctrl)
        left    = layouts.widgetbox(widgets["filtering"], **mode)
        bottom  = self._keyedlayout(ctrl, fig, left = left)
        return column(widgets["status"] + [bottom])

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

            label = (self._theme.ylabel if not self._config.consensus.normalize else
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
        if self._theme.showraw:
            get2 = lambda x: conc([np.NaN] if j else i for i in x for j in (0, 1))
            outp[2].update(z = get2(cycles), zmag  = get2(zmag))

        else:
            cons = self._plotmodel.getdisplay("consensus")
            if cons is not None:
                get0 = lambda i, j, k: conc([cons[i, j], cons[i, k][::-1]])
                outp[0].update(z     = get0("consensus", 0, 2),
                               zmag  = get0("zmag", "", ""),
                               zbead = get0(self._model.bead, 0, 2))
                outp[1].update(z     = cons["consensus", 1],
                               zmag  = cons["zmag", ""],
                               zbead = cons[self._model.bead, 1])
        return outp

class RampView(PlotView[RampPlotCreator]):
    "Peaks plot view"
    TASKS = ('extremumalignment',)
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(ctrl, tasks = self.TASKS)
