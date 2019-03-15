#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=protected-access
# pylint: disable=unused-import
""" access to files """
from ..testutils.bokehtesting import bokehaction, _ManagedServerLoop, LOGS
from .                        import path as _utpath

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
    return _utpath(path)
_ManagedServerLoop.path = staticmethod(_path)
