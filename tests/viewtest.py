#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests views """
from pytest                     import approx       # pylint: disable=no-name-in-module
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import

import anastore.control # pylint: disable=unused-import
import anastore

from view.toolbar               import ToolBar
from view.beadplot              import BeadPlotView, DpxKeyedRow
from view.cyclesplot            import CyclesPlotView

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

    with bokehaction.serve(CyclesPlotView, 'app.BeadsToolBar') as server:
        server.ctrl.observe("globals.current.plot.cycles", _printrng)
        server.load('big_legacy')

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        _press('Shift- ',           0., 0.)
        fig  = server.widget['Cycles:Hist']()
        assert fig.x_range.end                  > 2000.
        assert fig.extra_x_ranges['cycles'].end > 30.

        _press('Shift-ArrowUp',     0.275218, 0.475218)
        assert fig.x_range.end                  == approx(103, abs=.1)
        assert fig.extra_x_ranges['cycles'].end == approx(4,   abs=.1)

        _press('Alt-ArrowUp',       0.315218, 0.515218)
        _press('Alt-ArrowDown',     0.275218, 0.475218)
        _press('Shift-ArrowDown',  -0.124781, 0.875219)

        curr = server.ctrl.getGlobal("current")
        assert curr.bead in (None, 0)
        server.press('PageUp')
        assert curr.bead == 1

        yvals = server.ctrl.getGlobal("current.plot.cycles").y.get()
        assert yvals == approx((-0.124781, 0.875219), rel=1e-2)

        server.change('Cycles:Oligos', 'value', ' TGGC  , aatt')
        assert server.widget['Cycles:Oligos'].value == 'aatt, tggc'
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert cnf['config.plot.cycles']['oligos'] == ['aatt', 'tggc']

        server.change('Cycles:Oligos', 'value', '')
        assert server.widget['Cycles:Oligos'].value == ''
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert 'oligos' not in cnf.get('config.plot.cycles', {})

        server.load('hairpins.fasta', andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([0, 1000], abs = 1.))
        server.change('Cycles:Oligos',   'value', 'TgGC ')
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([166, 1113], abs = 1.))
        assert server.widget['Cycles:Stretch'].value == approx(0.88, abs = 1e-5)
        assert server.widget['Cycles:Bias'].value == approx(-.0816519, abs = 1e-5)
        server.change('Cycles:Bias',     'value', -.05)
        assert server.widget['Cycles:Bias'].value == approx(-.05, abs = 1e-5)
        server.change('Cycles:Stretch',  'value', .9)
        assert server.widget['Cycles:Stretch'].value == approx(0.9, abs = 1e-5)
        server.change('Cycles:Peaks',   ("source", "data","z"),  [0., .7])

        server.press('Ctrl-z')

if __name__ == '__main__':
    test_cyclesplot(bokehaction(None))
