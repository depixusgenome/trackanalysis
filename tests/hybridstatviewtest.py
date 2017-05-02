#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from tempfile                   import mktemp
from pytest                     import approx       # pylint: disable=no-name-in-module
import numpy as np

from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.plots                 import DpxKeyedRow
from hybridstat.reporting.identification import writeparams


def test_peaksplot(bokehaction):
    "test peaksplot"
    vals = [0.]*2
    def _printrng(evts):
        if 'y' in evts:
            vals[:2] = [0. if i is None else i for i in evts['y'].value]
    with bokehaction.launch('hybridstat.view.peaksplot.PeaksPlotView',
                            'app.BeadToolBar') as server:
        server.ctrl.observe("globals.project.plot.peaks", _printrng)
        server.ctrl.observe("rendered", lambda *_1, **_2: server.wait())
        server.load('big_legacy', andstop = False)

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, rel = 1e-2)

        fig = server.widget['Peaks:fig']()
        for _ in range(5):
            if fig.extra_x_ranges['duration'].end is None:
                server.wait()
        _press('Shift- ',         0.,       0.)
        _press('Shift-ArrowUp',   0.319146, 0.478953)
        _press('Alt-ArrowUp',     0.351107, 0.510914)
        _press('Alt-ArrowDown',   0.319146, 0.478953)
        _press('Shift-ArrowDown', 0.,       0.)

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

        out = mktemp()+"_hybridstattest100.xlsx"
        writeparams(out, [('GF3', (0,))])
        server.click('Peaks:IDPath', withpath = out)

        menu = server.widget['Cycles:Sequence'].menu
        lst  = tuple(i if i is None else i[0] for i in list(menu))
        assert lst == ('GF3', None, 'Select sequence')

def test_hybridstat(bokehaction):
    "test hybridstat"
    with bokehaction.launch('hybridstat.view', 'app.BeadToolBar') as server:
        server.change('Hybridstat:Tabs', 'active', 0)
        server.change('Hybridstat:Tabs', 'active', 1)
        server.change('Hybridstat:Tabs', 'active', 2)

        server.change('Hybridstat:Tabs', 'active', 1)
        server.load('big_legacy')

        server.change('Hybridstat:Tabs', 'active', 0)
        server.change('Hybridstat:Tabs', 'active', 1)
        server.change('Hybridstat:Tabs', 'active', 2)
        server.change('Hybridstat:Tabs', 'active', 0)
        server.change('Hybridstat:Tabs', 'active', 1)
        server.change('Hybridstat:Tabs', 'active', 2)

if __name__ == '__main__':
    test_peaksplot(bokehaction(None))
