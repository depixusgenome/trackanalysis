#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

def test_view_messages(bokehaction):
    "test the view"
    with bokehaction.launch('qualitycontrol.view', 'app.toolbar') as server:
        server.load('big_legacy')

def test_view_fov(bokehaction):
    "test the view"
    with bokehaction.launch('fov.FoVPlotView', 'app.toolbar') as server:
        server.load('big_legacy')

if __name__ == '__main__':
    test_view_messages(bokehaction(None))
