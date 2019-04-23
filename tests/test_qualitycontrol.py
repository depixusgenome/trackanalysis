#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from tests.testutils                  import integrationmark

@integrationmark
def test_view_messages(bokehaction):
    "test the view"
    bokehaction.start('qualitycontrol.view', 'taskapp.toolbar').load('big_legacy')

@integrationmark
def test_view_fov(bokehaction):
    "test the view"
    bokehaction.start(
        'fov.FoVPlotView',
        'taskapp.toolbar',
        filters = [
            [FutureWarning,      ".*elementwise comparison failed;.*"],
            [DeprecationWarning, ".*elementwise comparison failed.*"],
            [RuntimeWarning,     ".*All-NaN slice encountered.*"]
        ]
    ).load('big_legacy')

if __name__ == '__main__':
    from tests.testutils.bokehtesting import BokehAction
    test_view_messages(BokehAction(None))
