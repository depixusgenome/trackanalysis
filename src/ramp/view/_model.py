#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from   asyncio                  import wrap_future
from   concurrent.futures       import ProcessPoolExecutor
from   copy                     import deepcopy
from   typing                   import Dict, Any, Optional, List, Set

import pandas                   as     pd

from   model.plots              import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from   taskcontrol.beadscontrol import DataSelectionBeadController
from   taskcontrol.modelaccess  import TaskAccess, TaskPlotModelAccess
from   taskmodel.application    import TasksDisplay, InstrumentType
from   utils                    import initdefaults
from   view.base                import spawn
from   ..processor              import RampConsensusBeadProcessor, RampDataFrameProcessor


# pylint: disable=unused-import,wrong-import-order,ungrouped-imports
from   cleaning.processor.__config__       import DataCleaningTask
from   eventdetection.processor.__config__ import ExtremumAlignmentTask
from   ..__config__                        import RampConsensusBeadTask, RampStatsTask


class RampConfig:
    "ramp analysis with name"
    name      = "ramp"
    consensus = RampConsensusBeadTask(action    = ("percentile", dict(q = [25, 50, 75])),
                                      normalize = False)
    dataframe = RampStatsTask()
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def observe(self, ctrl):
        "update config to fit the cleaning task's"
        @ctrl.tasks.observe("addtask", "updatetask", "opentrack")
        def _ontasks(task = None, model = None, **_):
            if not isinstance(task, DataCleaningTask):
                task = next((i for i in model if isinstance(i, DataCleaningTask)), None)

            if (
                    isinstance(task, DataCleaningTask)
                    and (
                        task.minextent != self.dataframe.extension[0]
                        or task.maxextent != self.dataframe.extension[2]
                    )
            ):
                dframe           = deepcopy(self.dataframe)
                dframe.extension = (task.minextent, dframe.extension[1], task.maxextent)
                ctrl.theme.update(self, dataframe = dframe)

class RampPlotDisplay(PlotDisplay):
    """
    ramp plot display
    """
    name                               = "ramp"
    consensus: Dict[Any, pd.DataFrame] = {}
    dataframe: Dict[Any, pd.DataFrame] = {}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

    def status(self, root, disc) -> Dict[str, Set[int]]:
        "return the beads per status"
        data = self.dataframe.get(root, None)
        if data is None:
            return {}

        out  = {i: set(j) for i, j in data.groupby("status").bead.unique().items()}
        if isinstance(disc, (set, list)):
            disc = set(disc)
        else:
            disc = set(DataSelectionBeadController(disc).discarded)

        for i in out.values():
            i.difference_update(disc)
        out["discarded"] = disc
        return out

class RampPlotTheme(PlotTheme):
    """
    ramp plot theme
    """
    name             = "ramp.theme"
    consensusarea    = PlotAttrs('~gray', 'patch', 1, alpha = .5)
    consensusline    = PlotAttrs(consensusarea.color, 'line',  1, alpha = .5)
    beadarea         = PlotAttrs('~blue', 'patch', 1, alpha = .5)
    beadline         = PlotAttrs(beadarea.color, 'line',  1, alpha = .5)
    beadcycles       = PlotAttrs(beadarea.color, 'line',  1, alpha = .5)
    frames           = PlotAttrs("phase", 'o',  5, alpha = .25)
    phases           = "RdYlGn9"
    phaserange       = (..., ...)
    ylabelnormalized = "Z (% strand size)"
    xlabel           = 'Z magnet (mm)'
    figsize          = PlotTheme.defaultfigsize(500, 700)
    widgetwidth      = 500
    dataformat       = "raw"
    clip             = 99., .1
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,reset,save'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class RampPlotModel(PlotModel):
    """
    cleaning plot model
    """
    config  = RampConfig()
    theme   = RampPlotTheme()
    display = RampPlotDisplay()
    tasks   = TasksDisplay()
    def addto(self, ctrl, noerase = True):
        "sets-up model observers"
        super().addto(ctrl, noerase = noerase)
        self.tasks = ctrl.display.add(self.tasks, noerase)

    def getdisplay(self, name):
        "return the display for the current root task"
        return getattr(self.display, name).get(self.tasks.roottask, None)

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to ExtremumAlignmentTask"

class DataCleaningTaskAccess(TaskAccess, tasktype = DataCleaningTask):
    "access to ExtremumAlignmentTask"
    __DEFAULT = dict(
        minextent     = RampStatsTask().extension[0],
        maxextent     = RampStatsTask().extension[2],
        maxsaturation = 100.
    )
    def __init__(self, mdl):
        super().__init__(mdl)
        for dflt in (True, False):
            args = {
                i: dict(mdl.ctrl.theme.get("tasks", i, defaultmodel = dflt))
                for i in InstrumentType.__members__
            }
            for task in args.values():
                task['datacleaning'] = deepcopy(task['datacleaning'])
                for i, j in self.__DEFAULT.items():
                    setattr(task['datacleaning'], i, j)

            if dflt:
                mdl.ctrl.theme.updatedefaults("tasks", **args)
            else:
                mdl.ctrl.theme.update("tasks", **args)

    def observe(self, ctrl):
        "observe the RampStatsTask"
        @ctrl.theme.observe("ramp")
        def _onrampstatstask(old = (),  model = None, **_):
            if (
                    'dataframe' not in old
                    or self.task is None
                    or (
                        model.dataframe.extension[0] ==  self.task.minextent
                        and model.dataframe.extension[2] ==  self.task.maxextent
                    )
            ):
                return

            ctrl.tasks.updatetask(
                self.roottask,
                self.task,
                minextent = model.dataframe.extension[0],
                maxextent = model.dataframe.extension[2]
            )

class RampTaskPlotModelAccess(TaskPlotModelAccess):
    "access ramp task model"
    def __init__(self, ctrl) -> None:
        super().__init__(ctrl)
        self.cleaning  = DataCleaningTaskAccess(self)
        self.alignment = ExtremumAlignmentTaskAccess(self)

    def addto(self, ctrl, noerase = False):
        "add to the controller"
        self.cleaning.observe(ctrl)

def _run(cache, proc):
    return proc.dataframe(next(iter(cache.run())), **proc.config())

def observetracks(self: RampPlotModel, ctrl):
    "sets-up model observers"
    self.config.observe(ctrl)

    proctype                           = {"dataframe": RampDataFrameProcessor,
                                          "consensus": RampConsensusBeadProcessor}
    status: List[Optional[RampConfig]] = [None]
    def _consensus(info, root):
        if "consensus" in info:
            frame = info.get("dataframe", self.display.dataframe).get(root, None)
            assert frame is not None
            beads = frame[frame.status == "ok"].bead.unique()
            cons  = info["consensus"][root]
            RampConsensusBeadProcessor.consensus(cons, True, beads, "normalized")
            RampConsensusBeadProcessor.consensus(cons, False, beads, "consensus")

    def _poolcompute(iargs, **_):
        root  = self.tasks.roottask
        if root is None:
            return

        args  = set(proctype) & set(iargs)
        args |= {i for i in proctype if root not in getattr(self.display, i)}
        if len(args) == 0:
            return

        for name in args:
            getattr(self.display, name).pop(root, None)

        status[0] = stat = deepcopy(self.config)
        async def _thread():
            info  = {i: dict(getattr(self.display, i)) for i in args}
            procs = {i: proctype[i](task = getattr(self.config, i)) for i in args}
            cache = ctrl.tasks.processors(root, root)

            ctrl.display.handle({"ramp.pool"}, args = {'start': True, 'isgood': True})
            if stat is status[0]:
                with ProcessPoolExecutor(2) as pool:
                    subm = {i: wrap_future(pool.submit(_run, cache, j))
                            for i, j in procs.items()}
                    for i, j in subm.items():
                        info[i][root] = await j

            if stat is status[0]:
                _consensus(info, root)

            if stat is status[0]:
                status[0] = None
                ctrl.display.update(self.display, **info)
            ctrl.display.handle({"ramp.pool"},
                                args = {'start': False, 'isgood': stat is status[0]})

        spawn(_thread)

    @ctrl.tasks.observe
    def _onclosetrack(task = None, **_):
        for name in proctype:
            getattr(self.display, name).pop(task, None)

    @ctrl.display.observe(self.tasks)
    def _onchangetrack(**_):
        _poolcompute({i for i in proctype if self.getdisplay(i) is None})

    @ctrl.theme.observe(self.config)
    def _onchangeconfig(old = (), **_):
        data = self.getdisplay("dataframe")
        if "consensus" in old or data is None:
            _poolcompute(old)
            return

        info = {i: dict(getattr(self.display, i)) for i in proctype}
        data = RampDataFrameProcessor.status(data, self.config.dataframe)
        info["dataframe"][self.tasks.roottask] = data
        _consensus(info, self.tasks.roottask)
        ctrl.display.update(self.display, **info)
