#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from tempfile                   import mktemp, gettempdir
from pathlib                    import Path
from pytest                     import approx       # pylint: disable=no-name-in-module
import numpy as np

from tornado.gen                import sleep
from tornado.ioloop             import IOLoop

from testingcore                import path as utfilepath
from testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.plots                 import DpxKeyedRow

from peakfinding.reporting.batch         import createmodels as _pmodels

from hybridstat.reporting.identification import writeparams
from hybridstat.reporting.batch          import createmodels as _hmodels
from hybridstat.view._io                 import ConfigXlsxIO

def test_hybridstat_xlsxio():
    "tests xlxs production"
    itr  = _hmodels(dict(track     = (Path(utfilepath("big_legacy")).parent/"*.trk",
                                      utfilepath("CTGT_selection")),
                         sequence  = utfilepath("hairpins.fasta")))
    mdl  = next(itr)

    for path in Path(gettempdir()).glob("*_hybridstattest*.*"):
        path.unlink()

    out   = mktemp()+"_hybridstattest4.xlsx"
    assert not Path(out).exists()
    # pylint: disable=protected-access
    ConfigXlsxIO._run(dict(path      = out,
                           oligos    = 'CTGT',
                           sequences = utfilepath('hairpins.fasta')),
                      mdl)

    cnt = 0
    async def _run():
        nonlocal cnt
        for i in range(100):
            if ConfigXlsxIO.RUNNING is False:
                break
            cnt = i
            await sleep(.1)

    IOLoop.current().run_sync(_run)
    assert Path(out).exists()
    assert cnt > 0

def test_peaks_xlsxio():
    "tests xlxs production"
    itr  = _pmodels(dict(track = (Path(utfilepath("big_legacy")).parent/"*.trk",
                                  utfilepath("CTGT_selection"))))
    mdl  = next(itr)

    for path in Path(gettempdir()).glob("*_hybridstattest*.*"):
        path.unlink()

    out   = mktemp()+"_hybridstattest5.xlsx"
    assert not Path(out).exists()
    # pylint: disable=protected-access
    ConfigXlsxIO._run(dict(path      = out,
                           oligos    = [],
                           sequences = utfilepath('hairpins.fasta')),
                      mdl)

    cnt = 0
    async def _run():
        nonlocal cnt
        for i in range(100):
            if ConfigXlsxIO.RUNNING is False:
                break
            cnt = i
            await sleep(.1)

    IOLoop.current().run_sync(_run)
    assert Path(out).exists()
    assert cnt > 0

def test_peaksplot(bokehaction):
    "test peaksplot"
    vals = [0.]*2
    def _printrng(evts):
        if 'y' in evts:
            vals[:2] = [0. if i is None else i for i in evts['y'].value]
    with bokehaction.launch('hybridstat.view.peaksplot.PeaksPlotView',
                            'app.toolbar') as server:
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
        server.wait()
        assert server.widget['Cycles:Oligos'].value == 'ctgt'
        assert not all(np.isnan(src.data['distance']))
        assert not all(i.strip() == '' for i in src.data['orient'])

        menu = server.widget['Cycles:Sequence'].menu
        lst  = tuple(i if i is None else i[0] for i in list(menu))
        assert lst == ('GF2', 'GF4', 'GF1', 'GF3', '015', None, 'Select sequence')

        out = mktemp()+"_hybridstattest100.xlsx"
        writeparams(out, [('GF3', (0,))])
        server.click('Peaks:IDPath', withpath = out)
        server.wait()

        menu = server.widget['Cycles:Sequence'].menu
        lst  = tuple(i if i is None else i[0] for i in list(menu))
        assert lst == ('GF3', None, 'Select sequence')

def test_hybridstat(bokehaction):
    "test hybridstat"
    with bokehaction.launch('hybridstat.view', 'app.toolbar') as server:
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
