#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from   typing                   import Tuple
import numpy as np

from utils                      import NoArgs
from eventdetection.processor   import ExtremumAlignmentTask
from view.plots.tasks           import TaskPlotModelAccess, TaskAccess

from ..beadsubtraction          import BeadSubtractionTask
from ..processor                import DataCleaningTask

class DataCleaningAccess(TaskAccess):
    "access to data cleaning"
    def __init__(self, mdl):
        super().__init__(mdl, DataCleaningTask)

    @property
    def cache(self):
        "returns the object cache"
        tmp = super().cache
        mem = tmp() if callable(tmp) else None
        if mem is None:
            return None

        cur = mem.get(self.track, {}).get(self.bead, None)
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

class BeadSubtractionAccess(TaskAccess):
    "access to bead subtraction"
    def __init__(self, mdl):
        super().__init__(mdl, BeadSubtractionTask)

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

    def switch(self, bead):
        "adds or removes the bead"
        self.beads = set(self.beads).symmetric_difference({bead})

    @staticmethod
    def _configattributes(kwa):
        return {}

class DataCleaningModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.alignment  = TaskAccess(self, ExtremumAlignmentTask)
        self.cleaning   = DataCleaningAccess(self)
        self.subtracted = BeadSubtractionAccess(self)
        self.__bead: int                                          = None
        self.__colorstore: Tuple[int, np.ndarray, Tuple[int,...]] = None

    @property
    def colorstore(self):
        "returns the colorstore"
        if self.__colorstore is None or self.bead != self.__bead:
            return None

        return self.__colorstore

    @colorstore.setter
    def colorstore(self, val):
        "sets the colorstore"
        self.__bead       = self.bead
        self.__colorstore = val

    def clear(self):
        self.__bead = self.__colorstore = None
        super().clear()

    def reset(self) -> bool:
        self.__bead = self.__colorstore = None
        return super().reset()
