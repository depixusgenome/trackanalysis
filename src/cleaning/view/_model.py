#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"access to the model"
from   typing         import Tuple #pylint: disable=unused-import
import numpy as np

from eventdetection.processor   import ExtremumAlignmentTask
from view.plots.tasks           import TaskPlotModelAccess, TaskAccess

from ..processor                import DataCleaningTask, Partial

class DataCleaningAccess(TaskAccess):
    "access to data cleaning"
    __DEFAULT = (np.empty(0, dtype = 'i4'),)*2
    def __init__(self, mdl):
        super().__init__(mdl, DataCleaningTask)

    @property
    def cache(self):
        "returns the object cache"
        mem   = super().cache()
        cache = {} if mem is None else {i.name: i for i in mem.get(self.bead, ())}
        if cache is None:
            return cache

        for i in 'extent', 'hfsigma':
            cache.setdefault(i, Partial(i,  *self.__DEFAULT))
        return cache

    @property
    def badcycles(self):
        "returns bad cycles"
        mem   = super().cache()
        cache = None if mem is None else {i.name: i for i in mem.get(self.bead, ())}
        if cache is None:
            return np.ones(0, dtype = 'i4')
        return DataCleaningTask.badcycles(cache)

class DataCleaningModelAccess(TaskPlotModelAccess):
    "Model for Cycles View"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.alignment = TaskAccess(self, ExtremumAlignmentTask)
        self.cleaning  = DataCleaningAccess(self)
        self.colorstore = None # type: Tuple[int, np.ndarray, Tuple[int,...]]

    def reset(self) -> bool:
        self.colorstore = None
        return super().reset()
