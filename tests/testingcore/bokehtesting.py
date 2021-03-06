#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=protected-access
# pylint: disable=unused-import
""" access to files """
from ..testutils.bokehtesting import _ManagedServerLoop, LOGS, BokehAction
from .                        import path as utpath

def savedconfig(self):
    "return the saved config"
    from app.configuration          import ConfigurationIO
    import taskstore
    path = ConfigurationIO(self.ctrl).configpath(next(taskstore.iterversions('config')))
    return taskstore.load(path)

_ManagedServerLoop.savedconfig = property(savedconfig)

def _path(path):
    "returns the path to testing data"
    LOGS.debug("Test is opening: %s", path)
    return utpath(path)
_ManagedServerLoop.path = staticmethod(_path)
_ManagedServerLoop.roottask = property(lambda self: self.ctrl.display.get("tasks", "roottask"))
_ManagedServerLoop.track    = property(lambda self: self.ctrl.tasks.track(self.roottask))
def task(self, task):
    "returns a task"
    return self.ctrl.tasks.task(self.roottask, task)
_ManagedServerLoop.task = task

