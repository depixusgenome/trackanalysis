#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from   typing                   import Tuple
import numpy as np

from utils                      import NoArgs
from eventdetection.processor   import ExtremumAlignmentTask
from view.plots.tasks           import TaskPlotModelAccess, TaskAccess

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

        cur = mem.get(self.track, {}).get(self.bead, ())
        return None if cur is None else {i.name: i for i in cur[0]}

    def badcycles(self, cache = NoArgs):
        "returns bad cycles"
        return DataCleaningTask.badcycles(self.cache if cache is NoArgs else cache)

class DataCleaningModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.alignment = TaskAccess(self, ExtremumAlignmentTask)
        self.cleaning  = DataCleaningAccess(self)
        self.colorstore: Tuple[int, np.ndarray, Tuple[int,...]] = None

    def reset(self) -> bool:
        self.colorstore = None
        return super().reset()
