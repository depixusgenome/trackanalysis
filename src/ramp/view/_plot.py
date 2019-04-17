#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from    typing         import Dict, Tuple, List, Optional, cast
from    pathlib        import Path
import time

from    bokeh.models   import ColumnDataSource, Range1d
from    bokeh.plotting import Figure
from    bokeh          import layouts

import  numpy          as     np
import  pandas         as     pd

from    data.views             import Beads
from    taskview.plots         import PlotView, CACHE_TYPE, TaskPlotCreator
from    taskcontrol.taskio     import TaskIO
from    view.base              import spawn, ThreadPoolExecutor, threadmethod
from    utils.logconfig        import getLogger
from    utils.gui              import startfile

from    ._model                import (RampPlotModel, RampPlotTheme,
                                       RampPlotDisplay, RampTaskPlotModelAccess,
                                       observetracks)
from    ._widget               import RampWidgets

LOGS = getLogger(__name__)

class ConfigXlsxIOTheme:
    "ConfigXlsxIOTheme"
    name   = 'ramp.configxlsxio'
    maxiter= 10
    sleep  = .5
    start  = ('Report in progress ...', 'normal')
    end    = ('The report has been created', 'normal')
    errors = {'running': ("Can only create one report at a time", "warning")}

class ConfigXlsxIO(TaskIO):
    "Ana IO saving only the current project"
    EXT      = 'xlsx', 'csv'
    RUNNING  = False
    def __init__(self, ctrl):
        super().__init__(ctrl)
        self.__ctrl  = ctrl
        self.__theme = ctrl.theme.add(ConfigXlsxIOTheme(), True)

    def save(self, path:str, models):
        "creates a Hybridstat report"
        if not len(models):
            raise IOError("Nothing to save", "warning")

        def _end(exc):
            if exc is None and not Path(path).exists():
                exc = IOError("Report file created but not not found!")

            if isinstance(exc, IOError) and len(exc.args) == 1:
                if len(exc.args) == 1:
                    msg = self.__theme.errors.get(exc.args[0], None)
                    if msg is not None:
                        self.__msg(msg)
                        LOGS.debug('Failed report creation with %s', msg[0])
                        return
            if exc is not None:
                LOGS.exception(exc)
                self.__msg(exc)
            else:
                exc = self.__theme.end
                self.__msg(exc)
                startfile(path)

        try:
            LOGS.info('%s saving %s', type(self).__name__, path)
            ret = self._run(self.__theme, self.__ctrl.display.model("ramp"), path, models, _end)
        except IOError as exc:
            if len(exc.args) == 1:
                msg = self.__theme.errors.get(exc.args[0], None)
                if msg is not None:
                    raise IOError(*msg) from exc
            raise

        if ret:
            self.__msg(self.__theme.start)
        return ret

    def __msg(self, msg):
        self.__ctrl.display.update("message", message = msg)

    @classmethod
    def _run(   # pylint: disable=too-many-arguments
            cls, cnf, display, path, models, end = None
    ):
        "creates a Hybridstat report"
        if cls.RUNNING:
            raise IOError("running")
        cls.RUNNING = True

        def _pathname(root):
            path = root.path
            if isinstance(path, (tuple, list)):
                path = path[0]
            return Path(path).stem

        error: List[Optional[Exception]] = [None]
        def _process():
            try:
                for _ in range(cnf.maxiter):
                    if any(
                            mdl[0] not in display.dataframe
                            for mdl in models
                    ):
                        time.sleep(cnf.sleep)

                lst   = [
                    data[1].assign(filename = _pathname(data[0]))
                    for data in display.dataframe.items()
                    if any(data[0] is mdl[0] for mdl in models)
                ]
                if len(lst) == 0:
                    raise IOError("Failed to save data")
                frame = pd.concat(lst)
                if path.endswith(".xlsx"):
                    frame.to_excel(path)
                elif path.endswith(".pkz"):
                    frame.to_pickle(path)
                else:
                    frame.to_csv(path)
            except Exception as exc:
                error[0] = exc
                raise
            finally:
                cls.RUNNING = False
                if end is not None:
                    end(error[0])

        async def _thread():
            with ThreadPoolExecutor(1) as thread:
                await threadmethod(_process, pool = thread)

        spawn(_thread)
        return True

_DataType = Tuple[Dict[str, np.ndarray], ...]
class RampPlotCreator(TaskPlotCreator[RampTaskPlotModelAccess, RampPlotModel]):
    "Building the graph of cycles"
    _theme:         RampPlotTheme
    _display:       RampPlotDisplay
    _plotmodel:     RampPlotModel
    __src:          Tuple[ColumnDataSource,...]
    __fig:          Figure
    def __init__(self,  ctrl) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl, noerase = False)
        self.__widgets = RampWidgets(ctrl, self._plotmodel)

    def observe(self, ctrl, noerase = True):
        "sets-up model observers"
        super().observe(ctrl, noerase = noerase)
        self.__widgets.observe(self, ctrl)
        observetracks(self._plotmodel, ctrl)

        @ctrl.display.observe(self._display)
        def _ondataframes(old = (), **_):
            if len({"dataframe", "consensus"} & set(old)):
                self.reset(False)

        @ctrl.theme.observe(self._theme)
        def _ondisplaytype(old = (), **_):
            if "dataformat" in old:
                self.reset(False)

    def _addtodoc(self, ctrl, doc, *_): # pylint: disable=unused-argument
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
        self.linkmodeltoaxes(fig)

        mode = self.defaultsizingmode(width = self._theme.widgetwidth)
        left = layouts.widgetbox(self.__widgets.create(self, ctrl), **mode)
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

            self.setbounds(cache, self.__fig, extr("zmag"), extr("z"))

            label = (self._theme.ylabel if self._theme.dataformat != "norm" else
                     self._theme.ylabelnormalized)
            cache[self.__fig.yaxis[0]]["axis_label"] = label
            for i, j in zip(data, self.__src):
                cache[j]['data'] = i
            self.__widgets.reset(cache, disable)

    def __data(self, cycles, zmag) -> _DataType:
        empty           = np.empty(0, dtype = 'f4')
        outp: _DataType = tuple({i: empty for i in ("z", "zmag", "zbead")}
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

class RampPlotView(PlotView[RampPlotCreator]):
    "Peaks plot view"
    TASKS = ('extremumalignment',)
    def ismain(self, ctrl):
        "Cleaning and alignment, ... are set-up by default"
        self._ismain(
            ctrl,
            tasks  = self.TASKS,
            iosave = (..., __name__+".ConfigXlsxIO")
        )
