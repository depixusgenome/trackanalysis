#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from tests.testutils          import integrationmark
from tests.testingcore        import path as _utpath
from taskcontrol.beadscontrol import DataSelectionBeadController

@integrationmark
def test_toolbar(bokehaction):
    "test the toolbar"
    server = bokehaction.start('taskview.toolbar.BeadToolbar', 'taskapp.default')
    tbar = server.widget['Main:toolbar']
    ctrl = server.ctrl

    def _currtrack():
        return ctrl.display.get('tasks', 'roottask')

    def _checknone():
        assert tbar.frozen
        assert _currtrack() is None

    def _checkpath(name):
        track = _currtrack()
        assert not tbar.frozen
        assert str(track.path[0]) == _utpath(name)

    def _checkopen():
        _checkpath('small_legacy')
        track = ctrl.display.get('tasks', 'roottask')
        assert ctrl.theme.get("filedialog", "storage")["open"] == str(track.path[0])

    _checknone()
    server.load('small_legacy', rendered = "toolbardialog")
    _checkopen()
    server.press('Control-z')
    _checknone()
    server.press('Control-y')
    _checkopen()

    server.load('big_legacy', rendered = "toolbardialog")
    assert len(_currtrack().path) == 1
    _checkpath('big_legacy')

    proc = ctrl.display.get('tasks', 'taskcache')

    def _reset():
        server.press('Control-z')
        server.cmd(lambda: ctrl.display.update("tasks", taskcache = proc))
        assert len(_currtrack().path) == 1
        _checkpath('big_legacy')

    server.load('CTGT_selection', rendered = "toolbardialog")
    assert len(_currtrack().path) == 2
    assert str(_currtrack().path[1]) == _utpath('CTGT_selection')
    _checkpath('big_legacy')

    _reset()

    server.load(
        'CTGT_selection/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.cgr',
        rendered = "toolbardialog"
    )
    assert len(_currtrack().path) == 2
    assert str(_currtrack().path[1]) == _utpath('CTGT_selection')
    _checkpath('big_legacy')

    _reset()

    server.load(
        (
            'CTGT_selection/test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec.cgr',
            'CTGT_selection/Z(t)bd0track10.gr'
        ),
        rendered = "toolbardialog"
    )
    assert len(_currtrack().path) == 2
    assert str(_currtrack().path[1]) == _utpath('CTGT_selection/Z(t)bd0track10.gr')
    _checkpath('big_legacy')

@integrationmark
def test_beadtoolbar(bokehaction):
    "test the toolbar"
    server = bokehaction.start('taskview.toolbar.BeadToolbar', 'taskapp.default')
    beads  = DataSelectionBeadController(server.ctrl)

    server.load('big_legacy', rendered = "toolbardialog")
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

    server.load('CTGT_selection/Z(t)bd1track10.gr', rendered = "toolbardialog")
    assert frozenset(beads.availablebeads) == frozenset((1,))

    server.load('CTGT_selection/Z(t)bd0track10.gr', rendered = "toolbardialog")
    assert frozenset(beads.availablebeads) == frozenset((0, 1))

    server.change('Main:toolbar', 'discarded', '0')
    assert frozenset(beads.availablebeads) == frozenset((1,))

if __name__ == '__main__':
    # pylint: disable=ungrouped-imports
    from tests.testingcore.bokehtesting import BokehAction
    test_toolbar(BokehAction(None))
