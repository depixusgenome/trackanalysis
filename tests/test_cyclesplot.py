#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests cycles views """
import warnings
from pytest                   import approx       # pylint: disable=no-name-in-module
from tests.testutils          import integrationmark
from tests.testingcore.bokehtesting import bokehaction  # pylint: disable=unused-import
from view.plots               import DpxKeyedRow

def _check(server, name, value):
    if callable(value):
        for _ in range(5):
            if value():
                break
            server.wait()
        else:
            assert value()
        return
    for _ in range(5):
        if server.widget[name].value == value:
            break
        server.wait()
    else:
        assert server.widget[name].value == value

@integrationmark
def test_cyclesplot(bokehaction): # pylint: disable=too-many-statements
    "test cyclesplot basic stuff"
    vals = [0.]*2
    def _printrng(old = None, model = None, **_):
        if 'ybounds' in old:
            vals[:2] = [0. if i is None else i for i in model.ybounds]

    with bokehaction.launch('cyclesplot.CyclesPlotView', 'taskapp.toolbar',
                            runtime = "browser") as server:
        server.ctrl.display.observe("cycles", _printrng)
        server.load('big_legacy')

        old = [None, None]
        def _press(val):
            krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category = DeprecationWarning)
                server.press(val, krow)
                server.wait()
            assert vals != old
            old.clear()
            old.extend(val)

        fig  = server.widget['Cycles:Hist']()
        for _ in range(5):
            if fig.extra_x_ranges['cycles'].end == 0.0:
                server.wait()
        assert fig.x_range.end                  > 2000.
        assert fig.extra_x_ranges['cycles'].end > 50.

        _press('Shift- ')
        _press('Shift-ArrowUp')
        for _ in range(5):
            if fig.extra_x_ranges['cycles'].end > 1500.0:
                server.wait()
        assert fig.x_range.end                  < 1500.
        assert fig.extra_x_ranges['cycles'].end < 30.
        _press('Alt-ArrowUp')
        _press('Alt-ArrowDown')
        _press('Shift-ArrowDown')

        curr = server.ctrl.display.model("tasks")
        assert curr.bead in (None, 0)
        server.press('PageUp', andstop = False, rendered = True)
        assert curr.bead == 1
        server.change('Cycles:Oligos', 'value', ' TGGC  , aatt')
        _check(server, 'Cycles:Oligos', 'aatt, tggc')

        cnf  = server.savedconfig
        assert cnf['config.sequence']['probes'] == ['aatt', 'tggc']
        assert cnf['config.sequence']['history'] == [['aatt', 'tggc']]

        server.change('Cycles:Oligos', 'value', '')
        _check(server, 'Cycles:Oligos', '')
        cnf  = server.savedconfig
        assert not cnf['config.sequence'].get('probes', None)
        assert cnf['config.sequence']['history'] == [['aatt', 'tggc']]

        server.load('hairpins.fasta', rendered = False, andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        _check(
            server, '',
            lambda: (
                server.widget['Cycles:Peaks'].source.data['bases']
                == approx([0, 1000], abs = 1.)
            )
        )

        server.change('Cycles:Oligos',   'value', 'TgGC ')
        _check(
            server, '',
            lambda: (
                server.widget['Cycles:Peaks'].source.data['bases']
                == approx([166, 1113], abs = 1.)
            )
        )

        assert server.widget['Cycles:Stretch'].value == approx(1./8.8e-4, abs = 1e-1)
        assert server.widget['Cycles:Bias'].value == approx(.0014, abs = 5e-4)
        server.change('Cycles:Bias',     'value', -.05)
        _check(server, 'Cycles:Bias', approx(-.05, abs = 1e-5))
        server.change('Cycles:Stretch',  'value', 1050.)
        _check(server, 'Cycles:Stretch', approx(1050., abs = 1e-5))
        server.press('Control-z')

@integrationmark
def test_cyclesplot2(bokehaction):
    "test cyclesplot data actions"
    with bokehaction.launch('cyclesplot.CyclesPlotView', 'taskapp.toolbar',
                            runtime = "browser") as server:
        server.load('big_legacy')

        fig  = server.widget['Cycles:Hist']()
        assert fig.extra_x_ranges['cycles'].end > 70
        server.change('Cycles:Alignment', 'active', 0, rendered = True)
        assert server.widget['Cycles:Alignment'].active == 0
        _check(server, '', lambda: fig.extra_x_ranges['cycles'].end < 70)

        server.press('Control-z', rendered = True)
        assert server.widget['Cycles:Alignment'].active == 1
        _check(server, '', lambda: fig.extra_x_ranges['cycles'].end > 70)

        rng  = server.widget['Cycles:Raw']().x_range
        vals = rng.start, rng.end

        server.change('Cycles:EventDetection', 'active', [0], browser = False, rendered = True)
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
        server.change('Cycles:DriftWidget', 'value', [0], rendered = True)
        server.wait()

if __name__ == '__main__':
    from testutils.bokehtesting import BokehAction
    test_cyclesplot(BokehAction(None))
