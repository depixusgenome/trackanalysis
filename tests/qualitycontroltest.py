#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

def test_view_messages(bokehaction):
    "test the view"
    with bokehaction.launch('qualitycontrol.view', 'app.toolbar') as server:
        server.ctrl.observe("rendered", lambda *_1, **_2: server.wait())
        server.load('big_legacy', andstop = False)
