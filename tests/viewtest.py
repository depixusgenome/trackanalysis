#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests views """
from bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.toolbar   import ToolBar


def test_toolbar(bokehaction):          # pylint: disable=redefined-outer-name
    u"test the toolbar"
    with bokehaction.server(ToolBar, 'default') as server:
        ctrl = server.ctrl
        curr = ctrl.getGlobal('current')
        def _checknone():
            #assert len(server.box.children) == 3
            assert curr.get('track', default = None) is None
            assert curr.get('task',  default = None) is None

        def _checkopen():
            track = curr.track.get()
            #assert len(fact.box.children) == 4
            assert track.path  == server.path('small_legacy')
            assert track       is curr.task.get()
            assert ctrl.getGlobal('config').last.path.trk.get() == track.path

        _checknone()
        server.load('small_legacy')
        _checkopen()
        #server.press('Control-z')
        #_checknone()
        #server.press('Control-y')
        #_checkopen()
        server.quit()

if __name__ == '__main__':
    test_toolbar(bokehaction(None))
