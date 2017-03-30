#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests views """
from pytest                     import approx       # pylint: disable=no-name-in-module
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

import anastore.control # pylint: disable=unused-import
import anastore

from view.toolbar               import ToolBar
from view.beadplot              import BeadPlotView, DpxKeyedRow
from cyclesplot                 import CyclesPlotView

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

def test_beadplot(bokehaction):        # pylint: disable=redefined-outer-name
    u"test plot"
    vals = [0.]*4
    def _printrng(evts):
        if 'x' in evts:
            vals[:2] = evts['x'].value
        if 'y' in evts:
            vals[2:] = evts['y'].value

    with bokehaction.launch(BeadPlotView, 'app.ToolBar') as server:
        server.ctrl.observe("globals.current.plot.bead", _printrng)
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

def test_cyclesplot(bokehaction):        # pylint: disable=redefined-outer-name
    u"test plot"
    vals = [0.]*2
    def _printrng(evts):
        if 'y' in evts:
            vals[:2] = evts['y'].value

    with bokehaction.launch(CyclesPlotView, 'app.BeadsToolBar') as server:
        server.ctrl.getGlobal('config').tasks.default = []
        server.ctrl.observe("globals.current.plot.cycles", _printrng)
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
        curr = server.ctrl.getGlobal("current")
        assert curr.bead in (None, 0)
        server.press('PageUp')
        assert curr.bead == 1

        server.change('Cycles:Oligos', 'value', ' TGGC  , aatt')
        assert server.widget['Cycles:Oligos'].value == 'aatt, tggc'
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert cnf['config']['oligos'] == ['aatt', 'tggc']
        assert cnf['config']['oligos.history'] == [['aatt', 'tggc']]

        server.change('Cycles:Oligos', 'value', '')
        assert server.widget['Cycles:Oligos'].value == ''
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert 'oligos' not in cnf.get('config', {})
        assert cnf['config']['oligos.history'] == [['aatt', 'tggc']]

        server.load('hairpins.fasta', andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        assert server.widget['Cycles:Hist'].ygrid[0].ticker.usedefault is True
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([0, 1000], abs = 1.))

        server.change('Cycles:Oligos',   'value', 'TgGC ')
        assert server.widget['Cycles:Hist'].ygrid[0].ticker.usedefault is False
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([166, 1113], abs = 1.))

        assert server.widget['Cycles:Stretch'].value == approx(0.88, abs = 1e-5)
        assert server.widget['Cycles:Bias'].value == approx(-.0816519, abs = 1e-5)
        server.change('Cycles:Bias',     'value', -.05)
        assert server.widget['Cycles:Bias'].value == approx(-.05, abs = 1e-5)
        server.change('Cycles:Stretch',  'value', .9)
        assert server.widget['Cycles:Stretch'].value == approx(0.9, abs = 1e-5)
        server.press('Control-z')

def test_cyclesplot2(bokehaction):        # pylint: disable=redefined-outer-name
    u"test plot"

    with bokehaction.launch(CyclesPlotView, 'app.BeadsToolBar') as server:
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

if __name__ == '__main__':
    test_cyclesplot2(bokehaction(None))
