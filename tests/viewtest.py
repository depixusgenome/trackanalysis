#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from pytest                     import approx       # pylint: disable=no-name-in-module

from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.plots                 import DpxKeyedRow

def test_toolbar(bokehaction):
    "test the toolbar"
    with bokehaction.launch('view.toolbar.BeadToolbar', 'app.default') as server:
        tbar = server.widget['Main:toolbar']
        ctrl = server.ctrl
        curr = ctrl.getGlobal('project')
        def _checknone():
            assert tbar.frozen
            assert curr.get('track', default = None) is None
            assert curr.get('task',  default = None) is None

        def _checkopen():
            track = curr.track.get()
            assert not tbar.frozen
            assert track.path  == server.path('small_legacy')
            assert track       is curr.task.get()
            assert ctrl.getGlobal('css').last.path.trk.get() == track.path

        _checknone()
        server.load('small_legacy')
        _checkopen()
        server.press('Control-z')
        _checknone()
        server.press('Control-y')
        _checkopen()
        server.quit()

def test_beadtoolbar(bokehaction):
    "test the toolbar"
    with bokehaction.launch('view.toolbar.BeadToolbar', 'app.default') as server:
        # pylint: disable=protected-access
        beads = server.get('BeadToolbar', '_BeadToolbar__bead')._bdctrl

        server.load('big_legacy')
        assert frozenset(beads.availablebeads) == frozenset(range(39))

        server.change('Main:toolbar', 'discarded', '0,1,3')
        assert frozenset(beads.availablebeads) == (frozenset(range(39))-{0,1,3})

        server.change('Main:toolbar', 'discarded', '')
        assert frozenset(beads.availablebeads) == frozenset(range(39))

        bead1 = server.widget['Main:toolbar'].bead
        server.press('Shift-Delete')
        assert frozenset(beads.availablebeads) == frozenset(range(39))-{bead1}

        bead2 = server.widget['Main:toolbar'].bead
        server.press('Shift-Delete')
        assert frozenset(beads.availablebeads) == frozenset(range(39))-{bead1, bead2}

        server.load('CTGT_selection/Z(t)bd1track10.gr')
        assert frozenset(beads.availablebeads) == frozenset((1,))

        server.load('CTGT_selection/Z(t)bd0track10.gr')
        assert frozenset(beads.availablebeads) == frozenset((0, 1))

        server.change('Main:toolbar', 'discarded', '0')
        assert frozenset(beads.availablebeads) == frozenset((1,))

def test_beadplot(bokehaction):
    "test plot"
    vals = [0.]*4
    def _printrng(evts):
        if 'x' in evts:
            vals[:2] = [0. if i is None else i for i in evts['x'].value]
        if 'y' in evts:
            vals[2:] = [0. if i is None else i for i in evts['y'].value]

    with bokehaction.launch('view.beadplot.BeadPlotView', 'app.toolbar') as server:
        server.ctrl.observe("globals.project.plot.bead", _printrng)
        server.ctrl.observe("rendered", lambda *_1, **_2: server.wait())
        server.load('small_legacy', andstop = False)

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        _press('Shift- ',          0.,       0.,         0.,      0.)
        _press('Shift-ArrowUp',    0.,       0.,         0.41992, 0.65178)
        _press('Shift-ArrowRight', 851.7503, 951.2497,   0.41992, 0.65178)
        _press('Alt-ArrowLeft',    831.8504, 931.34982,  0.41992, 0.65178)
        _press('Alt-ArrowUp',      831.8504, 931.34982,  0.46629, 0.69815)
        _press('Alt-ArrowRight',   851.7503, 951.2497,   0.46629, 0.69815)
        _press('Alt-ArrowDown',    851.7503, 951.2497,   0.41992, 0.65178)
        _press('Shift-ArrowLeft',  0.,       0.,         0.41992, 0.65178)
        _press('Shift-ArrowDown',  0.,       0.,         0.,      0.)
        _press('Shift-ArrowUp',    0.,       0.,         0.41992, 0.65178)
        server.press('Ctrl-z')

if __name__ == '__main__':
    test_beadtoolbar(bokehaction(None))
