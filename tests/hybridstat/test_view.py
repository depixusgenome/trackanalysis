#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
""" Tests views """
from typing                     import cast
from tempfile                   import mktemp, gettempdir
from pathlib                    import Path
import warnings
import asyncio
import numpy as np

from bokeh.plotting             import Figure
from bokeh.models               import Tabs, FactorRange
from tornado.gen                import sleep
from tornado.ioloop             import IOLoop
from tornado.platform.asyncio   import AsyncIOMainLoop

from tests.testutils                  import integrationmark
from tests.testingcore                import path as utfilepath
from tests.testingcore.bokehtesting   import bokehaction  # pylint: disable=unused-import
from view.plots                 import DpxKeyedRow

from peakfinding.reporting.batch         import createmodels as _pmodels

with warnings.catch_warnings():
    warnings.filterwarnings(
        'ignore',
        category = DeprecationWarning,
        message  = ".*html argument of XMLParser.*"
    )
    from hybridstat.reporting.identification import writeparams

from hybridstat.reporting.batch          import createmodels as _hmodels
from hybridstat.view._io                 import ConfigXlsxIO
from peakcalling.processor.__config__    import FitToHairpinTask

@integrationmark
def test_hybridstat_xlsxio():
    "tests xlxs production"
    asyncio.set_event_loop(asyncio.new_event_loop())
    AsyncIOMainLoop().make_current()

    path  = cast(Path, utfilepath("big_legacy"))
    track = Path(path).parent/"*.trk", utfilepath("CTGT_selection")
    itr   = _hmodels(dict(track     = track, # type: ignore
                          sequence  = utfilepath("hairpins.fasta")))
    mdl   = next(itr)

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
        for i in range(50):
            if ConfigXlsxIO.RUNNING is False:
                break
            cnt = i
            await sleep(.5)

    try:
        IOLoop.current().run_sync(_run)
        assert Path(out).exists()
        assert cnt > 0
    finally:
        ConfigXlsxIO.RUNNING = False

@integrationmark
def test_peaks_xlsxio():
    "tests xlxs production"
    try:
        asyncio.set_event_loop(asyncio.new_event_loop())
        AsyncIOMainLoop().make_current()

        path = cast(Path, utfilepath("big_legacy"))
        itr  = _pmodels(dict(track = (Path(path).parent/"*.trk", utfilepath("CTGT_selection"))))
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
    finally:
        ConfigXlsxIO.RUNNING = False

def _t_e_s_t_peaks(server, bkact): # pylint: disable=too-many-statements
    import hybridstat.view._widget as widgetmod
    filt = server.widget[widgetmod.DpxFitParams]
    src  = server.widget['Peaks:List'].source
    root = server.ctrl.display.get("tasks", "roottask")
    assert filt.frozen
    assert all(np.isnan(src.data['distance']))
    assert all(i.strip() == '' for i in src.data['orient'])
    server.change('Cycles:Oligos', 'value', 'ctgt')
    assert all(np.isnan(src.data['distance']))
    assert all(i.strip() == '' for i in src.data['orient'])
    assert filt.frozen
    server.change('Cycles:Oligos', 'value', '')
    server.load('hairpins.fasta', rendered = False, andpress= False)
    server.change('Cycles:Sequence', 'value', '←')
    assert all(np.isnan(src.data['distance']))
    assert all(i.strip() == '' for i in src.data['orient'])
    assert filt.frozen

    server.change('Cycles:Oligos', 'value', 'ctgt', rendered = True)
    server.wait()
    assert server.widget['Cycles:Oligos'].value == 'ctgt'
    assert not all(np.isnan(src.data['distance']))
    assert not all(i.strip() == '' for i in src.data['orient'])
    assert not filt.frozen

    menu = server.widget['Cycles:Sequence'].menu
    lst  = tuple(i if i is None else i[0] for i in list(menu))
    assert lst == ('₁ GF4', '₂ GF1', '₃ GF2', '₄ GF3', '✗ 015',
                   None, 'Select a hairpin path')

    def _hascstr(yes):
        task  = server.ctrl.tasks.task(root, FitToHairpinTask)
        assert len(task.constraints) == yes

    server.change(filt, 'locksequence', True, rendered = True)
    _hascstr(1)

    server.change(filt, 'locksequence', False, rendered = True)
    _hascstr(0)

    server.change(filt, 'stretch', "1300", rendered = True)
    _hascstr(1)
    server.change(filt, 'stretch', "", rendered = True)
    _hascstr(0)

    out = mktemp()+"_hybridstattest100.xlsx"
    writeparams(out, [('GF3', (0,))])
    server.click('Peaks:IDPath', withpath = out)
    server.wait()

    menu = server.widget['Cycles:Sequence'].menu
    lst  = tuple(i if i is None else i[0] for i in list(menu))
    assert lst == ('₁ GF3', '✗ 015', '✗ GF1', '✗ GF2', '✗ GF4', None,
                   'Select a hairpin path')

    out = mktemp()+"_hybridstattest101.xlsx"
    found = [0]
    def _startfile(path):
        found[0] = path
    bkact.setattr(widgetmod, 'startfile', _startfile)
    server.click('Peaks:IDPath', withnewpath = out)
    server.wait()
    assert found[0] == out
    assert Path(out).exists()
    _hascstr(1)

@integrationmark
def test_peaksplot(bokehaction): # pylint: disable=too-many-statements,too-many-locals
    "test peaksplot"
    vals = [0.]*2
    prev = [1.]*2
    def _printrng(old = None, model = None, **_):
        if 'ybounds' in old:
            vals[:2] = [0. if i is None else i for i in model.ybounds]

    server = bokehaction.start(
        'hybridstat.view.peaksplot.PeaksPlotView',
        'taskapp.toolbar'
    )
    server.ctrl.display.observe("hybridstat.peaks", _printrng)
    server.load('big_legacy')

    krow = next(iter(server.doc.select(dict(type = DpxKeyedRow))))
    def _press(val):
        server.press(val, krow)
        for _ in range(5):
            if vals != prev:
                break
            server.wait()
        assert vals != prev
        prev[:2] = vals

    fig = server.widget['Peaks:fig']()
    for _ in range(5):
        if fig.extra_x_ranges['duration'].end is None:
            server.wait()
    _press('Shift- ')
    _press('Shift-ArrowUp')
    _press('Alt-ArrowUp')
    _press('Alt-ArrowDown')
    _press('Shift-ArrowDown')

    _t_e_s_t_peaks(server, bokehaction)

@integrationmark
def test_cyclehistplot(bokehaction): # pylint: disable=too-many-statements,too-many-locals
    "test peaksplot"
    server = bokehaction.start(
        'hybridstat.view.cyclehistplot.CycleHistPlotView',
        'taskapp.toolbar'
    )
    server.load('big_legacy')
    _t_e_s_t_peaks(server, bokehaction)

@integrationmark
def test_hairpingroup(bokehaction): # pylint: disable=too-many-statements,too-many-locals
    "test peaksplot"
    server = bokehaction.start(
        'hybridstat.view.hairpingroup.HairpinGroupPlotView',
        'taskapp.toolbar'
    )
    server.ctrl.theme.update("hybridstat.precomputations", ncpu = 0)
    server.load('big_legacy')
    rng  = server.widget.get(FactorRange)
    tbar = server.widget.get('Main:toolbar')
    filt = server.widget.get('HairpinGroup:filter')
    assert rng.factors == ['0']

    server.change(tbar, 'bead', tbar.bead+1, rendered = True)
    assert rng.factors == ['1', '0']

    server.load('hairpins.fasta', andpress = False, rendered = False)
    server.change('Cycles:Sequence', 'value', '←')
    server.change('Cycles:Oligos', 'value', 'ctgt', rendered = True)
    server.wait()
    assert rng.factors == ['1']

    server.change(tbar, 'bead', tbar.bead+1, rendered = True)
    assert rng.factors == ['2']

    server.change(tbar, 'bead', 0, rendered = True)
    assert rng.factors == ['0']

    server.change(tbar, 'bead', 4, rendered = True)
    assert rng.factors == ['4', '0']

    server.change(filt, 'forced', '2', rendered = True)
    server.change(tbar, 'bead', 2, rendered = True)
    server.change('Cycles:Sequence', 'value', 'GF1', rendered = True)
    assert rng.factors == ['2', '1']

    server.change('Cycles:Sequence', 'value', 'GF4', rendered = True)
    assert rng.factors == ['2', '0', '4']

    server.change(filt, 'discarded', '0', rendered = True)
    assert rng.factors == ['2', '4']

    server.change(tbar, 'bead', 4, rendered = True)
    assert rng.factors == ['4', '2']

@integrationmark
def test_reference(bokehaction):
    "test peaksplot"
    server = bokehaction.start(
        'hybridstat.view.peaksplot.PeaksPlotView',
        'taskapp.toolbar'
    )

    server.load('100bp_4mer/ref.pk')
    ref = server.ctrl.display.get("tasks", "roottask")

    server.load('100bp_4mer/AACG.pk')

    store = server.ctrl.display.model("hybridstat.fittoreference")
    assert server.widget['HS:reference'].value == '-1'
    assert store.reference is None

    server.change("HS:reference", 'value', "0")
    assert server.widget['HS:reference'].value == '0'
    assert store.reference is ref

    server.load('hairpins.fasta', andpress = False, rendered = False)
    server.change('Cycles:Sequence', 'value', '←')
    server.change('Cycles:Oligos', 'value', 'ctgt', rendered = True)

@integrationmark
def test_hybridstat(bokehaction):
    "test hybridstat"
    server = bokehaction.start(
        'hybridstat.view.HybridStatView',
        'taskapp.toolbar',
        filters = [
            (RuntimeWarning,     ".*All-NaN slice encountered.*"),
            (DeprecationWarning, ".*elementwise comparison failed;*"),
        ]
    )
    server.ctrl.theme.update("hybridstat.precomputations", ncpu = 0)
    tabs = next(iter(server.doc.select({'type': Tabs})))
    for i in range(len(tabs.tabs)):
        server.change(tabs, 'active', i)
        server.wait()

    mdl         = server.ctrl.theme.model("app.tabs")
    assert list(mdl.titles.values()) == [i.title for i in tabs.tabs]
    indcleaning = next(i for i, j in enumerate(mdl.titles) if j == 'cleaning')
    indcyc      = next(i for i, j in enumerate(mdl.titles) if j == 'cycles')
    server.change(tabs, 'active', indcleaning)
    server.load('big_legacy')

    for i in range(len(tabs.tabs)):
        server.change(tabs, 'active', i, rendered = i != indcleaning)
        if i == indcleaning:
            server.wait()

    server.change(tabs, 'active', indcleaning)
    server.wait()
    server.change('Cleaning:Filter', 'subtracted', "38", rendered = True)
    server.change('Main:toolbar', 'discarded', '38', rendered = True)
    server.change(tabs, 'active', indcyc)

@integrationmark
def test_muwells(bokehaction):
    "test hybridstat"
    import selenium.common.exceptions
    server = bokehaction.start(
        'hybridstat.view.HybridStatView',
        'taskapp.toolbar',
        filters = [
            (RuntimeWarning,     ".*All-NaN slice encountered.*"),
            (DeprecationWarning, ".*elementwise comparison failed;*"),
        ],
        runtime = 'selenium'
    )
    server.ctrl.theme.update("hybridstat.precomputations", ncpu = 0)

    tabs    = next(iter(server.doc.select({'type': Tabs})))
    muwells = dict(server.ctrl.theme.get("tasks", "muwells"))
    muwells['datacleaning'].maxsaturation = 90
    server.ctrl.theme.update("tasks", muwells = muwells)
    def _test(dim):
        active   = tabs.active
        for i in range(len(tabs.tabs)-2):
            server.change(tabs, 'active', i, rendered = i != active)
            if i == active:
                server.wait()

            if i == 0:
                continue

            for elem in server.selenium["//b", ...]:
                try:
                    text = elem.text
                    assert dim not in text
                except selenium.common.exceptions.StaleElementReferenceException:
                    pass

            for elem in server.selenium[".slick-column-name", ...]:
                try:
                    text = elem.text
                    assert dim not in text
                except selenium.common.exceptions.StaleElementReferenceException:
                    pass

            assert not any(
                dim in axis.axis_label
                for fig in server.doc.select(dict(type = Figure))
                for axis in fig.yaxis
            )

    server.load('muwells/W6N46_HPB20190107_W2_OR134689_cycle_1.9-2.10_TC10m.trk')
    _test('V)')
    server.load('muwells/W6N46_HPB20190107_OR134689_cycle_1.9-2.10_TC10m.txt')
    _test('m)')

if __name__ == '__main__':
    # pylint: disable=ungrouped-imports
    from tests.testutils.bokehtesting import BokehAction
    test_muwells(BokehAction(None))
