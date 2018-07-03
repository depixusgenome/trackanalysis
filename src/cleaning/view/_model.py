#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from typing                     import Optional, List, Dict, cast
import numpy as np

from utils                      import NoArgs, initdefaults
from model.task                 import RootTask
from model.plots                import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
# pylint: disable=unused-import
from control.modelaccess        import TaskPlotModelAccess, TaskAccess
from eventdetection.processor   import ExtremumAlignmentTask
from ..beadsubtraction          import BeadSubtractionTask, FixedBeadDetection, FIXED_LIST
from ..processor                import DataCleaningTask

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
        if astats is None:
            return (np.zeros(1, dtype = 'i4') if self.track is None     else
                    np.arange(self.track.ncycles, dtype = 'i4'))

        stats = astats if isinstance(astats, dict) else dict(astats)
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
        self.update(beads = sorted(vals), disabled = len(vals) == 0)

    def referencebeads(self) -> Optional[List[int]]:
        "return beads from the reference if they exist"
        track = self.track
        root  = self._ctrl.theme.get("fittoreference", "reference", None)
        if root is None or track is None:
            return None

        lst  = self._ctrl.tasks.tasklist(root)
        task = next((t for t in lst if isinstance(t, self.tasktype)), None)
        if task is None:
            return []

        mine  = set(track.beads.keys())
        beads = [i for i in cast(BeadSubtractionTask, task).beads if i in mine]
        return beads

    def switch(self, bead):
        "adds or removes the bead"
        self.beads = set(self.beads).symmetric_difference({bead})

    @staticmethod
    def _configattributes(kwa):
        return {}

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to bead subtraction"

class FixedBeadDetectionConfig(FixedBeadDetection):
    """
    Fixed bead detection configuration.

    Warning: the class name must end with Config in order for the config file to be
    good.
    """
    name = "fixedbeads"

class FixedBeadDetectionData:
    "For saving in the right place"
    name                             = "fixedbeads"
    data: Dict[RootTask, FIXED_LIST] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class FixedBeadDetectionModel:
    """
    Fixed bead detection
    """
    config: FixedBeadDetectionConfig
    data:   FixedBeadDetectionData
    def __init__(self, ctrl):
        self.config = ctrl.theme  .add(FixedBeadDetectionConfig(), False)
        self.data   = ctrl.display.add(FixedBeadDetectionData(), False)

    def addto(self, ctrl, noerase = False):
        "add to the controller"
        self.config = ctrl.theme  .add(self.config, noerase)
        self.data   = ctrl.display.add(self.data,   noerase)

        @ctrl.tasks.observe
        def _onclosetrack(task = None, **_):
            if task in self.data.data:
                info = dict(self.data.data)
                info.pop(task)
                ctrl.display.update(self.data, data = info)

    def current(self, ctrl, root:RootTask) -> FIXED_LIST:
        "returns bead ids for potential fixed beads"
        if root is None:
            return []

        beads = self.data.data.get(root, None)
        if beads is None:
            track = ctrl.tasks.track(root)
            if track is None:
                return []

            info  = dict(self.data.data)
            beads = info[root] = self.config(track.beads)
            ctrl.display.update(self.data, data = info)
        return beads

class DataCleaningModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl) -> None:
        super().__init__(ctrl)
        self.alignment  = ExtremumAlignmentTaskAccess(self)
        self.cleaning   = DataCleaningAccess(self)
        self.subtracted = BeadSubtractionAccess(self)
        self.fixedbeads = FixedBeadDetectionModel(ctrl)

    def addto(self, ctrl, name = "tasks", noerase = False):
        "set _tasksmodel to same as main"
        super().addto(ctrl, name, noerase)
        self.fixedbeads.addto(ctrl, noerase)

    @property
    def availablefixedbeads(self) -> FIXED_LIST:
        "return the availablefixed beads for the current track"
        return self.fixedbeads.current(self._ctrl, self.roottask)

class CleaningPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
    name             = "cleaning.theme"
    points           = PlotAttrs('color',  'circle', 1, alpha   = .5)
    figsize          = 500, 800, 'fixed'
    widgetwidth      = 470
    order            = ('aberrant', 'hfsigma', 'extent', 'population',
                        'pingpong', 'saturation', 'good')
    colors           = dict(good       = '#6baed6', # blue
                            hfsigma    = 'gold',
                            extent     = 'orange',
                            population = 'hotpink',
                            pingpong   = 'hotpink',
                            saturation = 'chocolate',
                            aberrant   = 'red')
    tooltips         = [(u'(cycle, t, z)', '(@cycle, $~x{1}, $data_y{1.1111})')]
    toolbar          = dict(PlotTheme.toolbar)
    toolbar['items'] = 'ypan,ybox_zoom,reset,save,dpxhover'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class CleaningPlotModel(PlotModel):
    """
    cleaning plot model
    """
    theme   = CleaningPlotTheme()
    display = PlotDisplay(name = "cleaning")
