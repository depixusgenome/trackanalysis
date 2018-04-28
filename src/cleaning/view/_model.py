#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from typing                     import Optional, List, Set, cast
import numpy as np

from utils                      import NoArgs
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
    def __init__(self, mdl):
        super().__init__(mdl)
        self.config.root.fixedbead.minextent.default = 0.25
        self.project.root.tasks.fittoreference.gui.reference.default = None

    @property
    def beads(self):
        "returns beads to subtract"
        return getattr(self.task, 'beads', [])

    @beads.setter
    def beads(self, vals):
        "returns beads to subtract"
        if len(vals) == 0:
            self.remove()
        else:
            self.update(beads = sorted(vals))

    def referencebeads(self) -> Optional[List[int]]:
        "return beads from the reference if they exist"
        track = self.track
        root  = self.project.root.tasks.fittoreference.gui.reference.get()
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
        lst   = self._ctrl.tasks.tasklist(self.roottask)
        if not lst:
            return set()

        clean = next((t for t in lst if isinstance(t, DataCleaningTask)), None)
        if not clean:
            return set()

        cache = self._ctrl.tasks.cache(self.roottask, clean)()
        if not cache:
            return set()

        minext = self.config.root.fixedbead.minextent.get()
        def _compute(itm):
            arr   = next((i.values for i in itm if i.name == 'extent'), None)
            if arr is None:
                return False

            valid = np.isfinite(arr)
            return np.sum(arr[valid] < minext) == np.sum(valid)

        return set(i for i, (j, _) in cache.items() if _compute(j))

class ExtremumAlignmentTaskAccess(TaskAccess, tasktype = ExtremumAlignmentTask):
    "access to bead subtraction"

class DataCleaningModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.alignment  = ExtremumAlignmentTaskAccess(self)
        self.cleaning   = DataCleaningAccess(self)
        self.subtracted = BeadSubtractionAccess(self)
