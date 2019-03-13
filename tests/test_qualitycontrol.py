#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
import warnings
from tests.testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

def test_view_messages(bokehaction):
    "test the view"
    with bokehaction.launch('qualitycontrol.view', 'taskapp.toolbar') as server:
        server.load('big_legacy')

def test_view_fov(bokehaction):
    "test the view"
    with warnings.catch_warnings():
        warnings.filterwarnings(
            'ignore',
            category = FutureWarning,
            message  = ".*elementwise comparison failed;.*"
        )
        warnings.filterwarnings(
            'ignore',
            category = DeprecationWarning,
            message  = ".*elementwise comparison failed.*"
        )
        warnings.filterwarnings(
            'ignore',
            category = RuntimeWarning,
            message  = ".*All-NaN slice encountered.*"
        )

        with bokehaction.launch('fov.FoVPlotView', 'taskapp.toolbar') as server:
            server.load('big_legacy')

if __name__ == '__main__':
    from testutils.bokehtesting import BokehAction
    test_view_messages(BokehAction(None))
