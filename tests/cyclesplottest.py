#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests cycles views """
from pytest                     import approx       # pylint: disable=no-name-in-module

from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.plots                 import DpxKeyedRow

def test_cyclesplot(bokehaction):
    "test cyclesplot basic stuff"
    import anastore
    vals = [0.]*2
    def _printrng(old = None, model = None, **_):
        print(model.ybounds, model.xbounds)
        if 'ybounds' in old:
            vals[:2] = [0. if i is None else i for i in model.ybounds]

    with bokehaction.launch('cyclesplot.CyclesPlotView', 'app.toolbar') as server:
        server.ctrl.display.observe("cycles", _printrng)
        server.load('big_legacy', rendered = True)

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        fig  = server.widget['Cycles:Hist']()
        for _ in range(5):
            if fig.extra_x_ranges['cycles'].end == 0.0:
                server.wait()
        assert fig.x_range.end                  > 2000.
        assert fig.extra_x_ranges['cycles'].end > 30.

        _press('Shift- ',          0.,       0.)
        _press('Shift-ArrowUp',    0.258410, 0.464449)
        assert fig.x_range.end                  == approx(103, abs=.1)
        assert fig.extra_x_ranges['cycles'].end == approx(4,   abs=.1)
        _press('Alt-ArrowUp',       0.299618, 0.505657)
        _press('Alt-ArrowDown',     0.258410, 0.464449)
        _press('Shift-ArrowDown',   0.,       0.)

        curr = server.ctrl.theme.model("tasks")
        assert curr.bead in (None, 0)
        server.press('PageUp', andstop = False)
        assert curr.bead == 1

        server.change('Cycles:Oligos', 'value', ' TGGC  , aatt')
        assert server.widget['Cycles:Oligos'].value == 'aatt, tggc'
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert cnf['config.sequence']['probes'] == ['aatt', 'tggc']
        assert cnf['config.sequence']['history'] == [['aatt', 'tggc']]

        server.change('Cycles:Oligos', 'value', '')
        assert server.widget['Cycles:Oligos'].value == ''
        cnf = anastore.load(server.ctrl.configpath(next(anastore.iterversions('config'))))
        assert not cnf['config.sequence'].get('probes', None)
        assert cnf['config.sequence']['history'] == [['aatt', 'tggc']]

        server.load('hairpins.fasta', andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([0, 1000], abs = 1.))

        server.change('Cycles:Oligos',   'value', 'TgGC ')
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

    with bokehaction.launch('cyclesplot.CyclesPlotView', 'app.toolbar') as server:
        server.load('big_legacy', rendered = True)

        fig  = server.widget['Cycles:Hist']()
        assert fig.extra_x_ranges['cycles'].end < 40
        server.change('Cycles:Alignment', 'active', 1)

        for _ in range(5):
            val = fig.extra_x_ranges['cycles'].end
            if val is not None and val > 70:
                break
            server.wait()
        assert server.widget['Cycles:Alignment'].active == 1
        assert fig.extra_x_ranges['cycles'].end > 70

        server.press('Control-z')
        for _ in range(5):
            val = fig.extra_x_ranges['cycles'].end
            if val is not None and val < 40:
                break
            server.wait()
        assert server.widget['Cycles:Alignment'].active == 0
        assert fig.extra_x_ranges['cycles'].end < 40

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

        server.press('Shift-Delete')
        server.wait()
        server.change('Cycles:Drift', 'value', [0])
        server.wait()
        server.wait()

if __name__ == '__main__':
    test_cyclesplot(bokehaction(None))
