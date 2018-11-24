#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from testingcore.bokehtesting   import bokehaction
from control.beadscontrol       import DataSelectionBeadController

def test_toolbar(bokehaction):
    "test the toolbar"
    with bokehaction.launch('view.toolbar.BeadToolbar', 'app.default') as server:
        tbar = server.widget['Main:toolbar']
        ctrl = server.ctrl
        curr = lambda: ctrl.display.get('tasks', 'roottask')
        def _checknone():
            assert tbar.frozen
            assert curr() is None

        def _checkpath(name):
            track = curr()
            assert not tbar.frozen
            assert str(track.path[0]) == server.path(name)

        def _checkopen():
            _checkpath('small_legacy')
            track = ctrl.display.get('tasks', 'roottask')
            assert ctrl.theme.get("filedialog", "storage")["open"] == str(track.path[0])

        _checknone()
        server.load('small_legacy', rendered = False)
        _checkopen()
        server.press('Control-z')
        _checknone()
        server.press('Control-y')
        _checkopen()

        server.load('big_legacy', rendered = False)
        assert len(curr().path) == 1
        _checkpath('big_legacy')

        track = curr()
        def _reset():
            server.press('Control-z')
            server.cmd(lambda: ctrl.display.update("tasks", roottask = track))
            assert len(curr().path) == 1
            _checkpath('big_legacy')

        server.load('CTGT_selection', rendered = False)
        assert len(curr().path) == 2
        assert str(curr().path[1]) == server.path('CTGT_selection')
        _checkpath('big_legacy')

        _reset()

        server.load('CTGT_selection/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.cgr',
                    rendered = False)
        assert len(curr().path) == 2
        assert str(curr().path[1]) == server.path('CTGT_selection')
        _checkpath('big_legacy')

        _reset()

        server.load(('CTGT_selection/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.cgr',
                     'CTGT_selection/Z(t)bd0track10.gr'),
                    rendered = False)
        assert len(curr().path) == 2
        assert str(curr().path[1]) == server.path('CTGT_selection/Z(t)bd0track10.gr')
        _checkpath('big_legacy')

        server.quit()

def test_beadtoolbar(bokehaction):
    "test the toolbar"
    with bokehaction.launch('view.toolbar.BeadToolbar', 'app.default') as server:
        # pylint: disable=protected-access
        beads = DataSelectionBeadController(server.ctrl)

        server.load('big_legacy', rendered = False)
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

        server.load('CTGT_selection/Z(t)bd1track10.gr', rendered = False)
        assert frozenset(beads.availablebeads) == frozenset((1,))

        server.load('CTGT_selection/Z(t)bd0track10.gr', rendered = False)
        assert frozenset(beads.availablebeads) == frozenset((0, 1))

        server.change('Main:toolbar', 'discarded', '0')
        assert frozenset(beads.availablebeads) == frozenset((1,))

if __name__ == '__main__':
    test_toolbar(bokehaction(None))
