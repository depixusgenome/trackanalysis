#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"test peakcalling views"
import os
import warnings
from   itertools                import repeat
import pytest
from   numpy.testing            import assert_allclose
from   cleaning.processor       import DataCleaningTask, ClippingTask
from   eventdetection.processor import ExtremumAlignmentTask, EventDetectionTask
from   peakfinding.processor    import PeakSelectorTask
from   peakcalling.processor    import FitToHairpinTask
from   peakcalling.view         import AxisConfig, FoVStatsPlot
from   peakcalling.view._statsplot import (     # pylint: disable=protected-access
    _BeadStatusPlot, _HairpinPlot, _PeaksPlot
)
from   taskmodel.track          import TrackReaderTask, DataSelectionTask
from   taskcontrol.taskcontrol  import create
from   taskcontrol.beadscontrol import DataSelectionBeadController
from   tests.testutils          import integrationmark
from   tests.testingcore        import path as utpath

_EVT  = 'peakcalling.view.jobs.stop'

class _Fig:
    extra_x_ranges = {'beadcount': 'beadcount'}
    x_range        = 'x_range'
    yaxis          = ['yaxis']
    xaxis          = ['xaxistop', 'xaxisbottom']

    @classmethod
    def create(cls, **kwa):
        "patch FoVStatsPlot to get rid of Bokeh objects"
        fov = FoVStatsPlot()
        setattr(fov, '_fig',     cls())
        setattr(fov, '_topaxis', '_topaxis')
        setattr(fov, '_stats',   '_stats')
        setattr(fov, '_points',  '_points')
        mdl = getattr(fov, '_model')
        cls.newtasks(mdl, **kwa)
        mdl.tasks.jobs.config.multiprocess = False
        return fov, mdl

    @staticmethod
    def newtasks(mdl, beads = None, withhp = False):
        "add a list of tasks to the model"
        lst = [
            TrackReaderTask(path = utpath("big_legacy")),
            DataCleaningTask(),
            ClippingTask(),
            ExtremumAlignmentTask(),
            EventDetectionTask(),
            PeakSelectorTask()
        ]
        if beads:
            lst.insert(1, DataSelectionTask(selected = list(beads)))
        if withhp:
            lst.append(FitToHairpinTask(
                sequences = utpath("hairpins.fasta"), oligos = "kmer"
            ))

        mdl.tasks.tasks.tasks.add(create(lst))

def _server(bokehaction, name, evt = _EVT):
    # pylint: disable=protected-access,unused-import,import-outside-toplevel
    filters = [
        (FutureWarning,      ".*elementwise comparison failed;.*"),
        (RuntimeWarning,     ".*All-NaN slice encountered.*"),
        (DeprecationWarning, ".*elementwise comparison failed;.*"),
        (DeprecationWarning, '.*Using or importing the ABCs from.*'),
        (DeprecationWarning, '.*the html argument of XMLParser.*'),
        (DeprecationWarning, '.*defusedxml.lxml is no longer supported and .*'),
    ]

    with warnings.catch_warnings():
        for i, j in filters:
            warnings.filterwarnings('ignore', category = i, message = j)
        import hybridstat.view._io  # noqa

    server = bokehaction.start(
        f'peakcalling.view.{name}',
        'taskapp.toolbar',
        filters = filters,
        runtime = 'selenium'
    )
    for i in ('beads', 'stats'):
        if f'peakcalling.view.{i}' in server.ctrl.theme:
            server.ctrl.theme.model(f'peakcalling.view.{i}').tracknames = "full"

    server.ctrl.theme.model("peakcalling.precomputations").multiprocess = (
        'TEAMCITY_PROJECT_NAME' not in os.environ
    )

    fig = getattr(getattr(server.view.views[0], '_mainview'), '_fig')
    server.load('big_legacy', rendered = evt)
    return server, fig

def _fovstatspeaks(bokehaction):
    "creates a server with 2 fovs"
    server, fig = _server(bokehaction, 'FoVStatsPlot', evt = True)

    def _cmd():
        bdctrl = DataSelectionBeadController(server.ctrl)
        avail  = list(bdctrl.availablebeads)
        with server.ctrl.action:
            bdctrl.setdiscarded(server.ctrl, set(avail[5:]))

    server.cmd(_cmd, rendered = _EVT)

    def _cmd2():
        bdctrl = DataSelectionBeadController(server.ctrl)
        avail  = list(bdctrl.availablebeads)
        with server.ctrl.action:
            bdctrl.setdiscarded(server.ctrl, set(avail[:5]+avail[10:]))

    server.load('big_legacy', rendered = True)
    server.cmd(_cmd2, rendered = _EVT)
    assert fig.yaxis[0].axis_label == "count (%)"

    modal = server.selenium.modal("//span[@class='icon-dpx-cog']", True)
    return (server, fig, modal)

def _fovstatshairpin(bokehaction):
    "creates a server with 2 fovs"
    server, fig, modal = _fovstatspeaks(bokehaction)
    _addhp(server)
    return server, fig, modal

@pytest.fixture
def fovstatspeaks(bokehaction):
    "creates a server with 2 fovs"
    return _fovstatspeaks(bokehaction)

@pytest.fixture
def fovstatshairpin(bokehaction):
    "creates a server with 2 fovs"
    return _fovstatshairpin(bokehaction)

def _addhp(server):
    server.cmd(
        lambda: server.ctrl.tasks.addtask(
            next(next(server.ctrl.tasks.tasklist(...))),
            FitToHairpinTask(sequences = utpath("hairpins.fasta"), oligos = "kmer")
        ),
        rendered = _EVT
    )

@integrationmark
def test_beadsplot(bokehaction):
    "test the view"
    server, fig = _server(bokehaction, 'BeadsScatterPlot')

    assert fig.x_range.factors == list(zip(
        repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
        [
            '0', '1', '2', '3', '4', '7', '8', '12', '13', '14', '17', '18', '23',
            '24', '25', '27', '33', '34', '35', '37'
        ]
    ))

    _addhp(server)

    assert fig.x_range.factors == [
        (j, i, k)
        for i, (j, k) in zip(
            repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
            [
                ('GF1', '14'), ('GF1', '33'), ('GF1', '1'), ('GF1', '7'), ('GF1', '34'),
                ('GF1', '12'), ('GF1', '35'),
                ('GF3', '27'), ('GF3', '13'), ('GF3', '3'), ('GF3', '17'), ('GF3', '37'),
                ('GF3', '23'), ('GF3', '18'),
                ('GF2', '25'), ('GF2', '2'),
                ('GF4', '0'), ('GF4', '4'), ('GF4', '24')
            ]
        )
    ]

    server.cmd(
        lambda: server.ctrl.display.update(
            'peakcalling.view.beads', hairpins = {'015', 'GF2', 'GF3', 'GF4'}
        ),
        rendered = True
    )

    assert fig.x_range.factors == [
        (j, i, k)
        for i, (j, k) in zip(
            repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
            [
                ('GF1', '14'), ('GF1', '33'), ('GF1', '1'), ('GF1', '7'), ('GF1', '34'),
                ('GF1', '12'), ('GF1', '35'),
            ]
        )
    ]

def test_statsplot_info_simple():
    "test the view without the view"
    # pylint: disable=protected-access
    fov, mdl = _Fig.create()

    # testing for when there is nothing to plot
    for cls in _BeadStatusPlot, _PeaksPlot, _HairpinPlot:
        assert dict(cls(fov, mdl.tasks.processors)._reset())['x_range']['factors'] == ['']

    def _change(tpe, xaxis = None, **kwa):
        if xaxis:
            kwa['xinfo'] = [AxisConfig(i) for i in xaxis]
        mdl.theme.__dict__.update(**kwa)
        cls = (
            _BeadStatusPlot if 'beadstatus' in mdl.theme.xaxis else
            _PeaksPlot      if tpe                             else
            _HairpinPlot
        )
        return dict(cls(fov, mdl.tasks.processors)._reset())

    def _checkbsfact(tpe: bool):
        cache   = _change(tpe, xaxis = ['track', 'beadstatus'], yaxis = 'bead')
        factors = [(i, j.replace('\u2063', '')) for i, j in cache['x_range']['factors']]
        vals    = ['ok', '% good', 'non-closing', 'Δz', 'σ[HF]', '∑|dz|']
        if not tpe:
            vals.insert(4, 'no blockages')
        assert factors == list(zip(
            repeat(''),
            vals
        ))

    def _check(tpe):
        mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))
        _checkbsfact(tpe)

        cache = _change(tpe, yaxis = 'hybridisationrate', xaxis = ['track'])
        source = cache['_stats']['data']
        for i, j in {
                'median':    [11.650485], 'boxcenter': [20.12945],
                'boxheight': [30.550162], 'bottom':    [0.970874], 'top': [76.699029]
        }.items():
            assert_allclose(source[i], j,  rtol = 5e-1, atol = 5e-1)

        cache   = _change(tpe, yaxis = 'hybridisationrate', xaxis = ['track', 'status'])
        factors = [(i, j.replace('\u2063', '')) for i, j in cache['x_range']['factors']]
        if tpe:
            assert factors == list(zip(
                repeat(''),
                ['baseline', 'blockage', 'single strand', '> single strand']
            ))
        else:
            assert factors == list(zip(
                repeat(''),
                [
                    'baseline', 'identified', 'missing', 'unidentified',
                    'single strand', '> single strand'
                ]
            ))

    _check(True)

    next(iter(mdl.tasks.tasks.tasks.tasks.values())).add(
        FitToHairpinTask(
            sequence = utpath("hairpins.fasta"),
            oligos   = "4mer",
        ),
        mdl.tasks.tasks.state.processors[FitToHairpinTask]
    )

    _check(False)

def test_statsplot_info_hpins():
    "test the view"
    # pylint: disable=protected-access
    fov, mdl = _Fig.create(beads = list(range(5)),     withhp = True)
    _Fig.newtasks(mdl, beads = list(range(5, 10)), withhp = True)

    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    def _change(xaxis = None, **kwa):
        if xaxis:
            kwa['xinfo'] = [AxisConfig(i) for i in xaxis]
        mdl.theme.__dict__.update(**kwa)
        cls = (
            _BeadStatusPlot if 'beadstatus' in mdl.theme.xaxis else
            _HairpinPlot
        )
        return dict(cls(fov, mdl.tasks.processors)._reset())

    cache = _change(yaxis = 'averageduration', xaxis = ['status'])
    assert cache['yaxis']['axis_label'] == "binding duration (s)"
    assert cache['x_range']['factors'] == [
        '\u2063baseline',
        '\u2063\u2063identified',
        '\u2063\u2063\u2063missing',
        '\u2063\u2063\u2063\u2063unidentified',
        '\u2063\u2063\u2063\u2063\u2063\u2063single strand',
        '\u2063\u2063\u2063\u2063\u2063\u2063\u2063> single strand'
    ]

    cache = _change(yaxis = 'bead', xaxis = ['hairpin'])
    assert cache['yaxis']['axis_label'] == "count (%)"
    assert cache['x_range']['factors'] == ['GF1', 'GF4', 'GF2', 'GF3']

    mdl.display.hairpins = {'GF2', 'GF3'}
    cache = _change()
    assert cache['yaxis']['axis_label'] == "count (%)"
    assert cache['x_range']['factors'] == ['GF1', 'GF4']

    mdl.display.hairpins = {}
    cache = _change(yaxis = "distance", xaxis = ["closest"])
    assert cache['yaxis']['axis_label'] == "Δ(binding - blockage) (bp)"
    assert cache['x_range']['factors'] == [
        '38.0', '46.0', '151.0', '157.0', '222.0', '258.0', '274.0', '294.0',
        '347.0', '357.0', '379.0', '393.0', '503.0', '540.0', '569.0', '576.0',
        '631.0', '659.0', '704.0', '738.0', '754.0', '784.0', '791.0', '795.0',
        '800.0'
    ]

    mdl.display.hairpins = {'GF2', 'GF3'}
    cache = _change(yaxis = "distance", xaxis = ["hairpin", "closest"])
    assert cache['yaxis']['axis_label'] == "Δ(binding - blockage) (bp)"
    assert cache['x_range']['factors'] == [
        ('GF1', '157.0'), ('GF1', '258.0'), ('GF1', '393.0'), ('GF1', '503.0'),
        ('GF1', '704.0'), ('GF1', '795.0'), ('GF4', '38.0'),  ('GF4', '294.0'),
        ('GF4', '347.0'), ('GF4', '569.0'), ('GF4', '738.0'), ('GF4', '791.0')
    ]

    mdl.display.hairpins = {'GF2', 'GF3', 'GF4'}
    cache = _change(yaxis = "bead", xaxis = ["closest", "orientation"])
    assert cache['yaxis']['axis_label'] == 'count (%)'
    assert cache['x_range']['factors'] == [
        ('157.0', '+'), ('258.0', '+'), ('393.0', '\u2063-'), ('503.0', '\u2063-'),
        ('704.0', '+'), ('795.0', '\u2063-')
    ]

    cache = _change(yaxis = "bead", xaxis = ["orientation", "closest"])
    assert cache['yaxis']['axis_label'] == 'count (%)'
    assert cache['x_range']['factors'] == [
        ('+', '157.0'), ('+', '258.0'), ('+', '704.0'),
        ('\u2063-', '393.0'), ('\u2063-', '503.0'), ('\u2063-', '795.0')
    ]

    cache = _change(yaxis = "fn", xaxis = ["hairpin"])
    assert cache['yaxis']['axis_label'] == 'missing (% bindings)'
    assert cache['x_range']['factors'] == ['GF1']

    cache = _change(yaxis = "fnperbp", xaxis = ["orientation"])
    assert cache['yaxis']['axis_label'] == 'missing (bp⁻¹)'
    assert cache['x_range']['factors'] == ['+', '\u2063-']

@integrationmark
def test_statsplot_view_simple(bokehaction):
    "test the view"

    def _change(rendered = True, xaxis = None, **kwa):
        if xaxis:
            kwa['xinfo'] = [AxisConfig(i) for i in xaxis]
        server.cmd(
            lambda: server.ctrl.theme.update('peakcalling.view.stats', **kwa),
            rendered = rendered
        )

    def _checkbsfact(tpe: bool):
        factors = [(i, j.replace('\u2063', '')) for i, j in fig.x_range.factors]
        vals    = ['ok', '% good', 'non-closing', 'Δz', 'σ[HF]', '∑|dz|']
        if not tpe:
            vals.insert(4, 'no blockages')
        assert factors == list(zip(
            repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
            vals
        ))

    def _check(tpe):
        _checkbsfact(tpe)

        _change(yaxis = 'hybridisationrate', xaxis = ['track'])
        source = fig.renderers[1].data_source.data
        for i, j in {
                'median':    [11.650485], 'boxcenter': [20.12945],
                'boxheight': [30.550162], 'bottom':    [0.970874], 'top': [76.699029]
        }.items():
            assert_allclose(source[i], j,  rtol = 5e-1, atol = 5e-1)

        _change(yaxis = 'hybridisationrate', xaxis = ['track', 'status'])
        factors = [(i, j.replace('\u2063', '')) for i, j in fig.x_range.factors]
        if tpe:
            assert factors == list(zip(
                repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
                ['baseline', 'blockage', 'single strand', '> single strand']
            ))
        else:
            assert factors == list(zip(
                repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
                [
                    'baseline', 'identified', 'missing', 'unidentified',
                    'single strand', '> single strand'
                ]
            ))

        _change(xaxis = ['track', 'beadstatus'], yaxis = 'bead', rendered = True)
        _checkbsfact(tpe)

    server, fig = _server(bokehaction, 'FoVStatsPlot')
    _check(True)
    _addhp(server)
    _check(False)

@integrationmark
def test_statsplot_view_peaks1(bokehaction):
    "test the view"
    server, fig = _server(bokehaction, 'FoVStatsPlot', evt = True)

    def _cmd():
        bdctrl = DataSelectionBeadController(server.ctrl)
        avail  = list(bdctrl.availablebeads)
        with server.ctrl.action:
            bdctrl.setdiscarded(server.ctrl, set(avail[5:]))

    server.cmd(_cmd, rendered = _EVT)

    def _cmd2():
        bdctrl = DataSelectionBeadController(server.ctrl)
        avail  = list(bdctrl.availablebeads)
        with server.ctrl.action:
            bdctrl.setdiscarded(server.ctrl, set(avail[:5]+avail[10:]))

    server.load('big_legacy', rendered = True)
    server.cmd(_cmd2, rendered = _EVT)

    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == [
        ('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '\u2063% good'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '\u2063non-closing'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '\u2063∑|dz|')
    ]

    modal = server.selenium.modal("//span[@class='icon-dpx-cog']", True)
    with modal:
        modal.tab("Bead Status")
        for i in (5, 6):  # '% good', 'non-closing'
            modal[f'//input[@name="beadstatustag[{i}]"]'] = "bad"
    server.wait()
    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == [
        ('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '\u2063bad'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '\u2063∑|dz|')
    ]

    with modal:
        modal.select("//select[@name='xinfo[0].name']", "tracktag")
    server.wait()
    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == [('none', 'ok'), ('none', '\u2063bad'), ('none', '\u2063∑|dz|')]

    with modal:
        modal.select("//select[@name='xinfo[0].name']", "status")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='yaxis']", "averageduration")
    server.wait()

    assert fig.x_range.factors == [
        '\u2063baseline',
        '\u2063\u2063\u2063\u2063\u2063blockage',
        '\u2063\u2063\u2063\u2063\u2063\u2063single strand',
        '\u2063\u2063\u2063\u2063\u2063\u2063\u2063> single strand'
    ]
    assert fig.yaxis[0].axis_label == "binding duration (s)"

    _addhp(server)
    assert fig.yaxis[0].axis_label == "binding duration (s)"
    assert fig.x_range.factors == [
        '\u2063baseline',
        '\u2063\u2063identified',
        '\u2063\u2063\u2063missing',
        '\u2063\u2063\u2063\u2063unidentified',
        '\u2063\u2063\u2063\u2063\u2063\u2063single strand'
    ]

@integrationmark
def test_statsplot_view_peaks2(fovstatspeaks):
    "test the view"
    server, fig, modal = fovstatspeaks
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "tracktag")
        modal.select("//select[@name='xinfo[1].name']", "xxx")

        modal.tab("Tracks")
        modal["//input[@name='tracktag[0]']"] = "aaa"
        modal["//input[@name='tracktag[1]']"] = "bbb"
    server.wait()

    assert fig.yaxis[0].axis_label == "count (%)"
    assert set(fig.x_range.factors) == {'aaa', 'bbb'}
    assert fig.extra_x_ranges['beadcount'].factors == ['5', '2']

    with modal:
        modal.tab("Tracks")
        modal["//input[@name='beadmask[0]']"] = "0, 1"
    server.wait()

    assert fig.yaxis[0].axis_label == "count (%)"
    assert set(fig.x_range.factors) == {'aaa', 'bbb'}
    assert fig.extra_x_ranges['beadcount'].factors == ['3', '2']

@integrationmark
def test_statsplot_view_hpins1(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "status")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='yaxis']", "averageduration")
    server.wait()

    assert fig.yaxis[0].axis_label == "binding duration (s)"
    assert fig.x_range.factors == [
        '\u2063baseline',
        '\u2063\u2063identified',
        '\u2063\u2063\u2063missing',
        '\u2063\u2063\u2063\u2063unidentified',
        '\u2063\u2063\u2063\u2063\u2063\u2063single strand'
    ]

@integrationmark
def test_statsplot_view_hpins2(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "hairpin")
        modal.select("//select[@name='yaxis']", "bead")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
    server.wait()

    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == ['GF4', 'GF1', 'GF2', 'GF3']

    with modal:
        modal.tab("Hairpins")
        for i in (2, 3):
            modal.driver.execute_script(
                f"arguments[0].removeAttribute('checked')",
                modal[f"//input[@name='hairpinsel[{i}]']"]
            )
    server.wait()

    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == ['GF4', 'GF1']

@integrationmark
def test_statsplot_view_hpins3(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "closest")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='xinfo[2].name']", "xxx")
        modal.select("//select[@name='yaxis']", "distance")
    server.wait()

    assert fig.yaxis[0].axis_label == "Δ(binding - blockage) (bp)"
    assert fig.x_range.factors == [
        '38.0', '46.0', '151.0', '157.0', '222.0', '258.0', '274.0', '294.0',
        '347.0', '357.0', '379.0', '393.0', '503.0', '540.0', '569.0', '576.0',
        '631.0', '659.0', '704.0', '738.0', '754.0', '784.0', '791.0', '795.0',
        '800.0'
    ]

@integrationmark
def test_statsplot_view_hpins4(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "closest")
        modal.select("//select[@name='xinfo[1].name']", "orientation")
        modal.select("//select[@name='yaxis']", "bead")

        modal.tab("Hairpins")
        for i in (2, 3, 4):
            modal.driver.execute_script(
                f"arguments[0].removeAttribute('checked')",
                modal[f"//input[@name='hairpinsel[{i}]']"]
            )
    server.wait()

    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == [
        ('157.0', '+'), ('258.0', '+'), ('393.0', '\u2063-'), ('503.0', '\u2063-'),
        ('704.0', '+'), ('795.0', '\u2063-')
    ]

@integrationmark
def test_statsplot_view_hpins5(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "orientation")
        modal.select("//select[@name='xinfo[1].name']", "closest")
        modal.select("//select[@name='yaxis']", "bead")
        modal.tab("Hairpins")
        for i in (2, 3, 4):
            modal.driver.execute_script(
                f"arguments[0].removeAttribute('checked')",
                modal[f"//input[@name='hairpinsel[{i}]']"]
            )
    server.wait()
    assert fig.yaxis[0].axis_label == "count (%)"
    assert fig.x_range.factors == [
        ('+', '157.0'), ('+', '258.0'), ('+', '704.0'),
        ('\u2063-', '393.0'), ('\u2063-', '503.0'), ('\u2063-', '795.0')
    ]

@integrationmark
def test_statsplot_view_hpins6(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "hairpin")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='yaxis']", "fn")
        modal.tab("Hairpins")
        for i in (2, 3):
            modal.driver.execute_script(
                f"arguments[0].removeAttribute('checked')",
                modal[f"//input[@name='hairpinsel[{i}]']"]
            )
    server.wait()
    assert fig.yaxis[0].axis_label == "missing (% bindings)"
    assert fig.x_range.factors == ['GF1', 'GF4']

    with modal:
        modal.select("//select[@name='xinfo[0].name']", "orientation")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='yaxis']", "fnperbp")

    assert fig.yaxis[0].axis_label == 'missing (bp⁻¹)'
    assert fig.x_range.factors == ['+', '\u2063-']


if __name__ == '__main__':
    # test_statsplot_info_hpins()
    from tests.testingcore.bokehtesting import BokehAction
    with BokehAction(None) as bka:
        test_statsplot_view_hpins6(_fovstatshairpin(bka))
