#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests views """
from pytest                     import approx       # pylint: disable=no-name-in-module
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

import anastore.control # pylint: disable=unused-import

from view.toolbar               import ToolBar
from view.trackplot             import TrackPlot

def test_toolbar(bokehaction):          # pylint: disable=redefined-outer-name
    u"test the toolbar"
    with bokehaction.launch(ToolBar, 'app.Defaults') as server:
        save = server.get('ToolBar', 'tools')[1]
        ctrl = server.ctrl
        curr = ctrl.getGlobal('current')
        def _checknone():
            assert save.disabled, ('???', save, save.disabled)
            assert curr.get('track', default = None) is None
            assert curr.get('task',  default = None) is None

        def _checkopen():
            track = curr.track.get()
            assert not save.disabled, (save, save.disabled)
            assert track.path  == server.path('small_legacy')
            assert track       is curr.task.get()
            assert ctrl.getGlobal('config').last.path.trk.get() == track.path

        _checknone()
        server.load('small_legacy')
        _checkopen()
        server.press('Control-z')
        _checknone()
        server.press('Control-y')
        _checkopen()
        server.quit()

def test_trackplot(bokehaction):        # pylint: disable=redefined-outer-name
    u"test plot"
    vals = [0.]*4
    def _printrng(**evts):
        if 'x' in evts:
            vals[:2] = evts['x'].value
        if 'y' in evts:
            vals[2:] = evts['y'].value

    with bokehaction.launch(TrackPlot, 'app.ToolBar') as server:
        server.ctrl.observe("globals.current.plot.bead", _printrng)
        server.load('small_legacy')

        def _press(val, *truth):
            server.press(val, server.doc.roots[-1].children[-1].children[-1])
            assert vals == approx(truth, rel = 1e-2)

        _press('Shift- ',          652.7515, 1150.2485, -0.04378, 1.11549)
        _press('Shift-ArrowUp',    652.7515, 1150.2485,  0.41992, 0.65178)
        _press('Shift-ArrowRight', 851.7503, 951.2497,   0.41992, 0.65178)
        _press('Alt-ArrowLeft',    831.8504, 931.34982,  0.41992, 0.65178)
        _press('Alt-ArrowUp',      831.8504, 931.34982,  0.46629, 0.69815)
        _press('Alt-ArrowRight',   851.7503, 951.2497,   0.46629, 0.69815)
        _press('Alt-ArrowDown',    851.7503, 951.2497,   0.41992, 0.65178)
        _press('Shift-ArrowLeft',  652.7515, 1150.2484,  0.41992, 0.65178)
        _press('Shift-ArrowDown',  652.7515, 1150.2484, -0.04378, 1.11549)
        _press('Shift-ArrowUp',    652.7515, 1150.2484,  0.41992, 0.65178)
        server.press('Ctrl-z')

if __name__ == '__main__':
    test_toolbar(bokehaction(None))
