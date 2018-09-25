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

def test_peaksplot(bokehaction): # pylint: disable=too-many-statements
    "test peaksplot"
    vals = [0.]*2
    def _printrng(old = None, model = None, **_):
        if 'ybounds' in old:
            vals[:2] = [0. if i is None else i for i in model.ybounds]

    with bokehaction.launch('hybridstat.view.peaksplot.PeaksPlotView',
                            'app.toolbar') as server:
        server.ctrl.display.observe("hybridstat.peaks", _printrng)
        server.load('big_legacy')

        krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
        def _press(val, *truth):
            server.press(val, krow)
            assert vals == approx(truth, abs = 2e-2)

        fig = server.widget['Peaks:fig']()
        for _ in range(5):
            if fig.extra_x_ranges['duration'].end is None:
                server.wait()
        _press('Shift- ',         0.,       0.)
        _press('Shift-ArrowUp',   0.312381, 0.476166)
        _press('Alt-ArrowUp',     0.345138, 0.508923)
        _press('Alt-ArrowDown',   0.312381, 0.476166)
        _press('Shift-ArrowDown', 0.,       0.)

        src = server.widget['Peaks:List'].source
        assert all(np.isnan(src.data['distance']))
        assert all(i.strip() == '' for i in src.data['orient'])
        server.change('Cycles:Oligos', 'value', 'ctgt')
        assert all(np.isnan(src.data['distance']))
        assert all(i.strip() == '' for i in src.data['orient'])
        server.change('Cycles:Oligos', 'value', '')
        server.load('hairpins.fasta')
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
        assert lst == ('GF4', 'GF2', 'GF1', 'GF3', '015', None, 'Select sequence')

        out = mktemp()+"_hybridstattest100.xlsx"
        writeparams(out, [('GF3', (0,))])
        server.click('Peaks:IDPath', withpath = out)
        server.wait()

        menu = server.widget['Cycles:Sequence'].menu
        lst  = tuple(i if i is None else i[0] for i in list(menu))
        assert lst == ('GF3', None, 'Select sequence')

        out = mktemp()+"_hybridstattest101.xlsx"
        import hybridstat.view._widget as widgetmod
        found = [0]
        def _startfile(path):
            found[0] = path
        bokehaction.setattr(widgetmod, 'startfile', _startfile)
        server.click('Peaks:IDPath', withnewpath = out)
        server.wait()
        assert found[0] == out
        assert Path(out).exists()
        assert server.ctrl.display.get("hybridstat.peaks", "constraints") is not None

        server.cmd((lambda: setattr(server.widget['Peaks:IDPath'], 'value', "")),
                   andstop = False)
        server.wait()
        assert server.ctrl.display.get("hybridstat.peaks", "constraints") is None

def test_reference(bokehaction):
    "test peaksplot"
    with bokehaction.launch('hybridstat.view.peaksplot.PeaksPlotView',
                            'app.toolbar') as server:

        server.load('100bp_4mer/ref.pk')
        ref = server.ctrl.display.get("tasks", "roottask")

        server.load('100bp_4mer/AACG.pk')

        store = server.ctrl.display.model("Hybridstat.fittoreference")
        assert server.widget['HS:reference'].value == '-1'
        assert store.reference is None

        server.change("HS:reference", 'value', "0")
        assert server.widget['HS:reference'].value == '0'
        assert store.reference is ref

        server.load('hairpins.fasta')
        server.change('Cycles:Oligos', 'value', 'ctgt')
        server.wait()

def test_hybridstat(bokehaction):
    "test hybridstat"
    with bokehaction.launch('hybridstat.view', 'app.toolbar') as server:
        tabs        = server.widget['Hybridstat:Tabs']
        indcleaning = next(i for i, j in enumerate(tabs.tabs) if j.title == 'Cleaning')
        indcyc      = next(i for i, j in enumerate(tabs.tabs) if j.title == 'Cycles')
        for i in range(len(tabs.tabs)):
            server.change('Hybridstat:Tabs', 'active', i)

        server.change('Hybridstat:Tabs', 'active', indcleaning)
        server.load('big_legacy')

        for i in range(len(server.widget['Hybridstat:Tabs'].tabs)):
            server.change('Hybridstat:Tabs', 'active', i)
            server.wait()

        server.change('Hybridstat:Tabs', 'active', indcleaning)
        server.change('Cleaning:Filter', 'subtracted', "38")
        server.wait()

        server.change('Main:toolbar', 'discarded', '38')
        server.wait()

        server.change('Hybridstat:Tabs', 'active', indcyc)
        server.wait()

if __name__ == '__main__':
    test_hybridstat(bokehaction(None))
