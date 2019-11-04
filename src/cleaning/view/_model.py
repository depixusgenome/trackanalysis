#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from typing                         import List, Dict, Tuple, Any
import numpy as np

# pylint: disable=unused-import
from eventdetection.processor.__config__ import ExtremumAlignmentTask
from model.plots                         import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from taskcontrol.modelaccess             import TaskPlotModelAccess, TaskAccess
from taskmodel                           import RootTask
from taskmodel.application               import rescalingevent, TasksModel
from taskmodel.track                     import RawPrecisionTask
from utils                               import NoArgs, initdefaults
from ..beadsubtraction                   import FixedBeadDetection, FixedList
from ..processor.__config__              import (
    DataCleaningTask, BeadSubtractionTask, ClippingTask, UndersamplingTask
)

class UndersamplingTaskAccess(TaskAccess, tasktype = UndersamplingTask):
    "access to undersampling task"

class DataCleaningAccess(TaskAccess, tasktype = DataCleaningTask):
    "access to data cleaning"
    @property
    def cache(self):
        "returns the object cache"
        mem = super().cache()
        if mem is None:
            return None

        cur = mem.get(self.bead, None)
        return None if cur is None else {i.name: i for i in cur[0]}

    @cache.setter
    def cache(self, value):
        "set the cache object"
        raise NotImplementedError()

    def saturatedcycles(self, cache):
        "returns saturated cycles"
        sat                = cache['saturation'].values
        sat[np.isnan(sat)] = 0.
        return np.nonzero(sat > self.task.maxdisttozero)

    def nbadcycles(self, cache = NoArgs) -> int:
        "returns the number of bad cycles"
        return len(self.badcycles(cache))

    def sorted(self, order, cache = NoArgs):
        "returns cycles ordered by category"
        astats = self.cache if cache is NoArgs else cache
        track  = self.track
        if astats is None:
            return (
                np.zeros(1, dtype = 'i4') if track is None     else
                np.arange(track.ncycles, dtype = 'i4')
            )

        stats = astats if isinstance(astats, dict) else dict(astats)
        if 'discarded' in stats:
            cpy = np.copy(stats['discarded'].values)
            nan = np.isnan(cpy)
            cpy[~nan] *= -1
            cpy[nan]   = np.nonzero(nan)[0]+1
            return np.argsort(cpy)

        res   = np.full(len(next(iter(stats.values())).values), -1, dtype = 'i4')
        for i, name in enumerate(order):
            stat = stats.get(name, None)
            if stat is not None:
                cur      = np.union1d(stat.min, stat.max)
                res[cur] = cur+i*len(res)

        cur      = np.arange(len(res), dtype = 'i4')[res == -1]
        res[cur] = cur+order.index('good')*len(res)
        return np.argsort(res)

    def badcycles(self, cache = NoArgs):
        "returns bad cycles"
        return DataCleaningTask.badcycles(self.cache if cache is NoArgs else cache)

class BeadSubtractionAccess(TaskAccess, tasktype = BeadSubtractionTask):
    "access to bead subtraction"
    @property
    def beads(self):
        "returns beads to subtract"
        return getattr(self.task, 'beads', [])

    @beads.setter
    def beads(self, vals):
        "returns beads to subtract"
        lst               = list(vals) if vals else []
        self.update(beads = sorted(lst), disabled = len(lst) == 0)

    def switch(self, bead):
        "adds or removes the bead"
        self.beads = set(self.beads).symmetric_difference({bead})

    @staticmethod
    def _configattributes(kwa):
        return {}

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to bead subtraction"

class ClippingTaskAccess(TaskAccess, tasktype = ClippingTask):
    "access to the ClippingTask"

class RawPrecisionTaskAccess(TaskAccess, tasktype = RawPrecisionTask):
    "access to the RawPrecisionTask"

class FixedBeadDetectionConfig(FixedBeadDetection):
    """
    Fixed bead detection configuration.

    Warning: the class name must end with Config in order for the config file to be
    good.
    """
    name:      str   = "fixedbeads"
    rescaling: float = 1.
    automate:  bool  = True

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class FixedBeadDetectionStore:
    """
    Fixed bead detection data
    """
    name                            = "fixedbeads"
    data: Dict[RootTask, FixedList] = {}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class FixedBeadDetectionModel:
    """
    Fixed bead detection info
    """
    def __init__(self):
        self.config:     FixedBeadDetectionConfig = FixedBeadDetectionConfig()
        self.store:      FixedBeadDetectionStore  = FixedBeadDetectionStore()
        self.tasksmodel: TasksModel               = TasksModel()

    def swapmodels(self, ctrl):
        "swap models with those existing in the controller"
        self.tasksmodel.swapmodels(ctrl)
        self.config = ctrl.theme.swapmodels(self.config)
        self.store  = ctrl.display.swapmodels(self.store)

    def observe(self, ctrl):
        "observe to a model"

        @ctrl.tasks.observe
        @ctrl.tasks.hashwith(self.store)
        def _onclosetrack(task = None, **_):
            data = self.store.data
            if task in data:
                info = dict(data)
                info.pop(task, None)
                ctrl.display.update(self.store, data = info)

        @ctrl.theme.observe(self.config)
        @ctrl.theme.hashwith(self.config)
        def _onchangeconfig(**_):
            info                                   = dict(self.store.data)
            info[self.tasksmodel.display.roottask] = self.__compute()
            ctrl.display.update(self.store, data = info)

        @ctrl.tasks.observe
        @ctrl.tasks.hashwith(self.store)
        def _onopentrack(calllater = None, isarchive = False, **_):
            if not self.config.automate or isarchive:
                return

            @calllater.append
            def _addsubtracted(*_1, **_2):
                _onchangeconfig()
                root  = self.tasksmodel.display.roottask
                assert root is not None

                beads = [i[-1] for i in self.store.data.get(root, ())]
                ctrl.tasks.addtask(
                    root,
                    BeadSubtractionTask(beads = beads),
                    index = self.tasksmodel.config.defaulttaskindex(
                        self.tasksmodel.display.tasklist,
                        BeadSubtractionTask,
                    )
                )

        @ctrl.theme.observe(self.tasksmodel.config)
        @ctrl.display.observe(self.tasksmodel.display)
        @ctrl.display.hashwith(self.store, self.config)
        def _ontasks(old = None, **_):
            done, cur, coeff = rescalingevent(ctrl, old, self.config.rescaling)
            if not done:
                ctrl.theme.update(self.config, rescaling = cur, **dict(self.config.zscaled(coeff)))

    @property
    def available(self) -> FixedList:
        "returns bead ids for potential fixed beads"
        return self.store.data.get(self.tasksmodel.display.roottask, [])

    def __compute(self, force = False):
        root = self.tasksmodel.display.roottask
        if root is None:
            return []

        track = self.tasksmodel.display.track
        if track is None:
            return []

        if not force and self.store.data.get(root, None):
            return self.store.data[root]

        return self.config(track.beads)

class DataCleaningModelAccess(TaskPlotModelAccess):  # pylint: disable=too-many-instance-attributes
    "Access to cleaning tasks"
    def __init__(self, **_):
        super().__init__()
        self.undersampling = UndersamplingTaskAccess(self)
        self.fixedbeads    = FixedBeadDetectionModel()
        self.alignment     = ExtremumAlignmentTaskAccess(self)
        self.clipping      = ClippingTaskAccess(self)
        self.rawprecision  = RawPrecisionTaskAccess(self)
        self.cleaning      = DataCleaningAccess(self)
        self.subtracted    = BeadSubtractionAccess(self)

    @property
    def availablefixedbeads(self) -> FixedList:
        "returns bead ids for potential fixed beads"
        return self.fixedbeads.available

class CleaningPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name:          str                  = "cleaning.theme"
    lines:         PlotAttrs            = PlotAttrs('~gray', '-', 1, alpha                = .3)
    points:        PlotAttrs            = PlotAttrs('color', 'o', 1, alpha                = .5)
    hover:         PlotAttrs            = PlotAttrs('white', 'o', 4, alpha                = 0.)
    figsize:       Tuple[int, int, str] = PlotTheme.defaultfigsize(300, 500)
    clip:          int                  = 3
    clipovershoot: float                = 10
    maxfixedbeads: int                  = 15
    widgetwidth:   int                  = 535
    ntitles:       int                  = 5
    order:         Tuple[str,...]       = (
        'aberrant', 'hfsigma', 'extent', 'population',
        'pingpong', 'alignment', 'clipping', 'saturation', 'good'
    )
    colors:        Dict[str, str]       = dict(
        good       = '#6baed6',  # blue
        hfsigma    = 'gold',
        extent     = 'orange',
        population = 'hotpink',
        pingpong   = 'firebrick',
        saturation = 'chocolate',
        alignment  = 'darkgray',
        clipping   = 'darkorchid',
        aberrant   = 'red'
    )
    tooltips: List[Tuple[str, ...]] = [
        ('(cycle, t, z, status)', '(@cycle, $~x{1}, $data_y{1.1111}, @status)')
    ]
    toolbar:  Dict[str, Any]        = dict(
        PlotTheme.toolbar,
        items = 'pan,box_zoom,ypan,ybox_zoom,ywheel_zoom,reset,save,dpxhover'
    )
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class CleaningPlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = CleaningPlotTheme()
    display = PlotDisplay(name = "cleaning")
