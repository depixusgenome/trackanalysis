#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=protected-access
""" access to files """
from testutils.bokehtesting import bokehaction, _ManagedServerLoop # pylint: disable=unused-import

def savedconfig(self):
    "return the saved config"
    from app.configuration          import ConfigurationIO
    import taskstore
    path = ConfigurationIO(self.ctrl).configpath(next(taskstore.iterversions('config')))
    return taskstore.load(path)

_ManagedServerLoop.savedconfig = property(savedconfig)
