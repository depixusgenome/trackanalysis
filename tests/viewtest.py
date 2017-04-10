#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from pytest                     import approx       # pylint: disable=no-name-in-module
import numpy as np

from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.plots                 import DpxKeyedRow

def test_toolbar(bokehaction):
    "test the toolbar"
    with bokehaction.launch('view.toolbar.ToolBar', 'app.Defaults') as server:
        save = server.get('ToolBar', 'tools')[1]
        ctrl = server.ctrl
        curr = ctrl.getGlobal('project')
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

def test_beadtoolbar(bokehaction):
    "test the toolbar"
    with bokehaction.launch('view.toolbar.BeadToolBar', 'app.Defaults') as server:
        beads = server.get('BeadToolBar', '_beads')

        # pylint: disable=protected-access
        assert beads.input.disabled
        server.load('big_legacy')
        assert frozenset(beads._BeadInput__beads) == frozenset(range(39))

        server.load('CTGT_selection/Z(t)bd1track10.gr')
        assert frozenset(beads._BeadInput__beads) == frozenset((1,))

        server.load('CTGT_selection/Z(t)bd0track10.gr')
        assert frozenset(beads._BeadInput__beads) == frozenset((0, 1))

def test_beadplot(bokehaction):
    "test plot"
    vals = [0.]*4
    def _printrng(evts):
        if 'x' in evts:
            vals[:2] = evts['x'].value
        if 'y' in evts:
            vals[2:] = evts['y'].value

    with bokehaction.launch('view.beadplot.BeadPlotView', 'app.ToolBar') as server:
        server.ctrl.observe("globals.project.plot.bead", _printrng)
        server.load('small_legacy')

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        _press('Shift- ',          0., 0.,  0., 0.)
        _press('Shift-ArrowUp',    0., 0.,               0.41992, 0.65178)
        _press('Shift-ArrowRight', 851.7503, 951.2497,   0.41992, 0.65178)
        _press('Alt-ArrowLeft',    831.8504, 931.34982,  0.41992, 0.65178)
        _press('Alt-ArrowUp',      831.8504, 931.34982,  0.46629, 0.69815)
        _press('Alt-ArrowRight',   851.7503, 951.2497,   0.46629, 0.69815)
        _press('Alt-ArrowDown',    851.7503, 951.2497,   0.41992, 0.65178)
        _press('Shift-ArrowLeft',  652.7515, 1150.2484,  0.41992, 0.65178)
        _press('Shift-ArrowDown',  652.7515, 1150.2484, -0.04378, 1.11549)
        _press('Shift-ArrowUp',    652.7515, 1150.2484,  0.41992, 0.65178)
        server.press('Ctrl-z')

def test_cyclesplot(bokehaction):
    "test cyclesplot basic stuff"
    import anastore
    vals = [0.]*2
    def _printrng(evts):
        if 'y' in evts:
            vals[:2] = evts['y'].value

    with bokehaction.launch('cyclesplot.CyclesPlotView', 'app.BeadToolBar') as server:
        server.ctrl.getGlobal('config').tasks.default = []
        server.ctrl.observe("globals.project.plot.cycles", _printrng)
        server.load('big_legacy')

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        fig  = server.widget['Cycles:Hist']()
        for _ in range(5):
            if fig.extra_x_ranges['cycles'].end is None:
                server.wait()
        assert fig.x_range.end                  > 2000.
        assert fig.extra_x_ranges['cycles'].end > 30.

        _press('Shift- ',           0., 0.)


        _press('Shift-ArrowUp',    0.258410, 0.464449)
        assert fig.x_range.end                  == approx(103, abs=.1)
        assert fig.extra_x_ranges['cycles'].end == approx(4,   abs=.1)

        _press('Alt-ArrowUp',       0.299618, 0.505657)
        _press('Alt-ArrowDown',     0.258410, 0.464449)
        _press('Shift-ArrowDown',  -0.153668, 0.876528)
        curr = server.ctrl.getGlobal("project")
        assert curr.bead in (None, 0)
        server.press('PageUp')
        assert curr.bead == 1

        server.change('Cycles:Oligos', 'value', ' TGGC  , aatt')
        assert server.widget['Cycles:Oligos'].value == 'aatt, tggc'
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert cnf['config']['oligos'] == ['aatt', 'tggc']
        assert cnf['config.plot']['oligos.history'] == [['aatt', 'tggc']]

        server.change('Cycles:Oligos', 'value', '')
        assert server.widget['Cycles:Oligos'].value == ''
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert 'oligos' not in cnf.get('config', {})
        assert cnf['config.plot']['oligos.history'] == [['aatt', 'tggc']]

        server.load('hairpins.fasta', andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        assert server.widget['Cycles:Hist'].ygrid[0].ticker.usedefault is True
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([0, 1000], abs = 1.))

        server.change('Cycles:Oligos',   'value', 'TgGC ')
        assert server.widget['Cycles:Hist'].ygrid[0].ticker.usedefault is False
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([166, 1113], abs = 1.))

        assert server.widget['Cycles:Stretch'].value == approx(1./8.8e-4, abs = 1e-1)
        assert server.widget['Cycles:Bias'].value == approx(-.092152, abs = 1e-5)
        server.change('Cycles:Bias',     'value', -.05)
        assert server.widget['Cycles:Bias'].value == approx(-.05, abs = 1e-5)
        server.change('Cycles:Stretch',  'value', 1050.)
        assert server.widget['Cycles:Stretch'].value == approx(1050., abs = 1e-5)
        server.press('Control-z')

def test_cyclesplot2(bokehaction):
    "test cyclesplot data actions"

    with bokehaction.launch('cyclesplot.CyclesPlotView', 'app.BeadToolBar') as server:
        server.ctrl.getGlobal('config').tasks.default = []
        server.load('big_legacy')

        fig  = server.widget['Cycles:Hist']()
        assert fig.extra_x_ranges['cycles'].end < 50
        server.change('Cycles:Alignment', 'active', 1)

        for _ in range(5):
            val = fig.extra_x_ranges['cycles'].end
            if val is not None and val > 80:
                break
            server.wait()
        assert server.widget['Cycles:Alignment'].active == 1
        assert fig.extra_x_ranges['cycles'].end > 80

        server.press('Control-z')
        for _ in range(5):
            val = fig.extra_x_ranges['cycles'].end
            if val is not None and val < 80:
                break
            server.wait()
        assert server.widget['Cycles:Alignment'].active == 0
        assert fig.extra_x_ranges['cycles'].end < 50

        rng  = server.widget['Cycles:Raw']().x_range
        vals = rng.start, rng.end

        server.change('Cycles:EventDetection', 'active', [0], browser = False)
        for _ in range(5):
            val = rng.end
            if val is not None and val < 400:
                break
            server.wait()
        assert rng.start > vals[0]
        assert rng.end   < vals[1]
        assert rng.end   < 350

def test_peaksplot(bokehaction):
    "test peaksplot"
    vals = [0.]*2
    def _printrng(evts):
        if 'y' in evts:
            vals[:2] = evts['y'].value
    with bokehaction.launch('hybridstat.view.peaksplot.PeaksPlotView',
                            'app.BeadToolBar') as server:
        server.ctrl.observe("globals.project.plot.peaks", _printrng)
        server.load('big_legacy')

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        fig = server.widget['Peaks:fig']()
        for _ in range(5):
            if fig.extra_x_ranges['duration'].end is None:
                server.wait()
        _press('Shift- ',         0.,       0.)
        _press('Shift-ArrowUp',   0.216678, 0.377610)
        _press('Alt-ArrowUp',     0.248864, 0.409797)
        _press('Alt-ArrowDown',   0.216678, 0.377610)
        _press('Shift-ArrowDown', -0.10518, 0.699475)

        src = server.widget['Peaks:List'].source
        assert all(np.isnan(src.data['distance']))
        assert all(i.strip() == '' for i in src.data['orient'])
        server.change('Cycles:Oligos', 'value', 'ctgt')
        assert all(np.isnan(src.data['distance']))
        assert all(i.strip() == '' for i in src.data['orient'])
        server.change('Cycles:Oligos', 'value', '')
        server.load('hairpins.fasta', andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        assert all(np.isnan(src.data['distance']))
        assert all(i.strip() == '' for i in src.data['orient'])

        server.change('Cycles:Oligos', 'value', 'ctgt')
        assert server.widget['Cycles:Oligos'].value == 'ctgt'
        assert not all(np.isnan(src.data['distance']))
        assert not all(i.strip() == '' for i in src.data['orient'])

        menu = server.widget['Cycles:Sequence'].menu
        lst  = tuple(i if i is None else i[0] for i in list(menu))
        assert lst == ('GF4', 'GF2', 'GF1', 'GF3', '015', None, 'Select sequence')

if __name__ == '__main__':
    test_peaksplot(bokehaction(None))
