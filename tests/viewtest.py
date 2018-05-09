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
        curr = ctrl.globals.project
        def _checknone():
            assert tbar.frozen
            assert curr.get('track', default = None) is None
            assert curr.get('task',  default = None) is None

        def _checkpath(name):
            track = curr.track.get()
            assert not tbar.frozen
            assert str(track.path[0]) == server.path(name)

        def _checkopen():
            _checkpath('small_legacy')
            track = curr.track.get()
            assert track       is curr.task.get()
            assert ctrl.globals.css.last.path.trk.get() == str(track.path[0])

        _checknone()
        server.load('small_legacy')
        _checkopen()
        server.press('Control-z')
        _checknone()
        server.press('Control-y')
        _checkopen()

        server.load('big_legacy')
        assert len(curr.track.get().path) == 1
        _checkpath('big_legacy')

        track = curr.track.get()
        def _reset():
            server.press('Control-z')
            server.cmd(lambda: curr.track.set(track))
            assert len(curr.track.get().path) == 1
            _checkpath('big_legacy')

        server.load('CTGT_selection')
        assert len(curr.track.get().path) == 2
        assert str(curr.track.get().path[1]) == server.path('CTGT_selection')
        _checkpath('big_legacy')

        _reset()

        server.load('CTGT_selection/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.cgr')
        assert len(curr.track.get().path) == 2
        assert str(curr.track.get().path[1]) == server.path('CTGT_selection')
        _checkpath('big_legacy')

        _reset()

        server.load(('CTGT_selection/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.cgr',
                     'CTGT_selection/Z(t)bd0track10.gr'))
        assert len(curr.track.get().path) == 2
        assert str(curr.track.get().path[1]) == server.path('CTGT_selection/Z(t)bd0track10.gr')
        _checkpath('big_legacy')

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

if __name__ == '__main__':
    test_toolbar(bokehaction(None))
