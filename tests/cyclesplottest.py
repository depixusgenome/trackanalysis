#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests cycles views """
import warnings
from pytest                   import approx       # pylint: disable=no-name-in-module
from testingcore.bokehtesting import bokehaction  # pylint: disable=unused-import
from view.plots               import DpxKeyedRow

def test_cyclesplot(bokehaction): # pylint: disable=too-many-statements
    "test cyclesplot basic stuff"
    vals = [0.]*2
    def _printrng(old = None, model = None, **_):
        if 'ybounds' in old:
            vals[:2] = [0. if i is None else i for i in model.ybounds]

    with bokehaction.launch('cyclesplot.CyclesPlotView', 'app.toolbar',
                            runtime = "browser") as server:
        server.ctrl.display.observe("cycles", _printrng)
        server.load('big_legacy')

        def _press(val, *truth):
            krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category = DeprecationWarning)
                server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        fig  = server.widget['Cycles:Hist']()
        for _ in range(5):
            if fig.extra_x_ranges['cycles'].end == 0.0:
                server.wait()
        assert fig.x_range.end                  > 2000.
        assert fig.extra_x_ranges['cycles'].end > 30.

        _press('Shift- ',           0.,       0.)
        _press('Shift-ArrowUp',     0.359869, 0.564043)
        assert fig.x_range.end                  == approx(530, abs=.1)
        assert fig.extra_x_ranges['cycles'].end == approx(17,   abs=.1)
        _press('Alt-ArrowUp',       0.400703, 0.604878)
        _press('Alt-ArrowDown',     0.359869, 0.564043)
        _press('Shift-ArrowDown',   0.,       0.)

        curr = server.ctrl.display.model("tasks")
        assert curr.bead in (None, 0)
        server.press('PageUp', andstop = False)
        assert curr.bead == 1

        server.change('Cycles:Oligos', 'value', ' TGGC  , aatt')
        assert server.widget['Cycles:Oligos'].value == 'aatt, tggc'
        cnf  = server.savedconfig
        assert cnf['config.sequence']['probes'] == ['aatt', 'tggc']
        assert cnf['config.sequence']['history'] == [['aatt', 'tggc']]

        server.change('Cycles:Oligos', 'value', '')
        assert server.widget['Cycles:Oligos'].value == ''
        cnf  = server.savedconfig
        assert not cnf['config.sequence'].get('probes', None)
        assert cnf['config.sequence']['history'] == [['aatt', 'tggc']]

        server.load('hairpins.fasta', rendered = False, andpress = False)
        server.change('Cycles:Sequence', 'value', '←')
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([0, 1000], abs = 1.))

        server.change('Cycles:Oligos',   'value', 'TgGC ')
        assert (server.widget['Cycles:Peaks'].source.data['bases']
                == approx([166, 1113], abs = 1.))

        assert server.widget['Cycles:Stretch'].value == approx(1./8.8e-4, abs = 1e-1)
        assert server.widget['Cycles:Bias'].value == approx(.0014, abs = 5e-4)
        server.change('Cycles:Bias',     'value', -.05)
        assert server.widget['Cycles:Bias'].value == approx(-.05, abs = 1e-5)
        server.change('Cycles:Stretch',  'value', 1050.)
        assert server.widget['Cycles:Stretch'].value == approx(1050., abs = 1e-5)
        server.press('Control-z')

def test_cyclesplot2(bokehaction):
    "test cyclesplot data actions"
    with bokehaction.launch('cyclesplot.CyclesPlotView', 'app.toolbar',
                            runtime = "browser") as server:
        server.load('big_legacy')

        fig  = server.widget['Cycles:Hist']()
        assert fig.extra_x_ranges['cycles'].end > 70
        server.change('Cycles:Alignment', 'active', 0, rendered = True)
        assert server.widget['Cycles:Alignment'].active == 0
        assert fig.extra_x_ranges['cycles'].end < 70

        server.press('Control-z', rendered = True)
        assert server.widget['Cycles:Alignment'].active == 1
        assert fig.extra_x_ranges['cycles'].end > 70

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
    test_cyclesplot2(bokehaction(None))
