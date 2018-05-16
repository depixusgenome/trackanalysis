#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from typing                     import Optional, List, Set, cast
import numpy as np

from utils                      import NoArgs, initdefaults
from model.plots                import PlotAttrs, PlotTheme, PlotModel
# pylint: disable=unused-import
from control.modelaccess        import TaskPlotModelAccess, TaskAccess
from eventdetection.processor   import ExtremumAlignmentTask
from ..beadsubtraction          import BeadSubtractionTask
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

        mine  = set(track.beadsonly.keys())
        beads = [i for i in cast(BeadSubtractionTask, task).beads if i in mine]
        return beads

    def switch(self, bead):
        "adds or removes the bead"
        self.beads = set(self.beads).symmetric_difference({bead})

    @staticmethod
    def _configattributes(kwa):
        return {}

    def possiblefixedbeads(self) -> Set[int]:
        "returns bead ids with extent == all cycles"
        mdl = self._ctrl.theme.model("qc") if "qc" in self._ctrl.theme else None
        return mdl.fixedbeads(self._ctrl.tasks, self.roottask) if mdl else set()

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to bead subtraction"

class DataCleaningModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.alignment  = ExtremumAlignmentTaskAccess(self)
        self.cleaning   = DataCleaningAccess(self)
        self.subtracted = BeadSubtractionAccess(self)

class CleaningPlotTheme(PlotTheme):
    """
    cleaning plot theme
    """
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
