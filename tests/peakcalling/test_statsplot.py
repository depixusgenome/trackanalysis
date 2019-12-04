#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,unused-argument,protected-access
"test peakcalling views"
from   itertools                              import repeat
from   numpy.testing                          import assert_allclose
import numpy as np
from   bokeh.models                           import Range1d
from   cleaning.processor                     import DataCleaningTask, ClippingTask
from   eventdetection.processor               import ExtremumAlignmentTask, EventDetectionTask
from   peakfinding.processor                  import PeakSelectorTask
from   peakcalling.processor                  import FitToHairpinTask
from   peakcalling.model                      import AxisConfig, Slice
from   peakcalling.view                       import FoVStatsPlot
from   peakcalling.view._widgets._plot        import PeakcallingPlotModel
from   peakcalling.view.statsplot._hairpin    import _HairpinPlot
from   peakcalling.view.statsplot._beadstatus import _BeadStatusPlot
from   peakcalling.view.statsplot._peak       import _PeaksPlot
from   taskmodel.track                        import TrackReaderTask, DataSelectionTask
from   taskcontrol.taskcontrol                import create
from   taskcontrol.beadscontrol               import DataSelectionBeadController
from   tests.testutils                        import integrationmark
from   tests.testingcore                      import path as utpath

def _check_validity(fig, name = 'count (%)'):
    if isinstance(fig, dict):
        assert fig['yaxis']['axis_label'] == name
        stats = fig['_stats']['data']
    else:
        assert fig.yaxis[0].axis_label == name
        stats = fig.renderers[0].data_source.data

    if name == "count (%)":
        for i in ('bottom', 'top'):
            assert np.isfinite(stats[i]).sum() == 0
        assert_allclose(stats['boxcenter']*2., stats['boxheight'], atol = 1e-5, rtol = 1e-5)
        return

    for i in ('bottom', 'top'):
        assert np.isnan(stats[i]).sum() == 0

    assert np.all(stats['bottom'] <= stats['boxcenter'])
    assert np.all(stats['top']    >= stats['boxcenter'])

class _Fig:
    class _Rend:
        class glyph:  # pylint: disable=invalid-name,missing-class-docstring
            width = 10.
            name  = 'bars'

    visible        = 'visible'
    extra_x_ranges = {'beadcount': 'beadcount'}
    x_range        = 'x_range'
    y_range        = type('y_range', (), {'start': 0, 'end': 1})
    yaxis          = ['yaxis']
    xaxis          = ['xaxistop', 'xaxisbottom']
    renderers      = [_Rend]

    @classmethod
    def create(cls, **kwa):
        "patch FoVStatsPlot to get rid of Bokeh objects"
        fov = FoVStatsPlot()
        setattr(fov, '_fig',     cls())
        setattr(fov, '_topaxis', '_topaxis')
        setattr(fov, '_stats',   '_stats')
        setattr(fov, '_points',  '_points')
        mdl = getattr(fov, '_model')
        mdl.theme.linear = False
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

def _export(fov, tmp_path):
    tmp_path = tmp_path.with_suffix(".xlsx")
    if tmp_path.exists():
        tmp_path.unlink()
    assert fov.export(str(tmp_path))
    assert tmp_path.exists()

def test_statsplot_info_simple(diskcaching, tmp_path):
    "test the view without the view"
    fov, mdl = _Fig.create()

    # testing for when there is nothing to plot
    for cls in _BeadStatusPlot, _PeaksPlot, _HairpinPlot:
        assert (
            dict(cls(fov, mdl.tasks.processors)._reset())['x_range']['factors']
            == [('',)*3]
        )

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
        factors = [(i, j, k.replace('\u2063', '')) for i, j, k in cache['x_range']['factors']]
        vals    = ['ok', '% good', 'non-closing', 'Δz', 'σ[HF]', '∑|dz|']

        if not tpe:
            vals.insert(4, 'no blockages')
        assert set(factors) == set(zip(repeat(""), repeat(""), vals))

    def _check(tpe):
        mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))
        _checkbsfact(tpe)
        if tpe:
            _export(fov, tmp_path)

        cache = _change(tpe, yaxis = 'hybridisationrate', xaxis = ['track'])
        source = cache['_stats']['data']
        for i, j in {
                'median':    [11.650485], 'boxcenter': [20.12945],
                'boxheight': [30.550162], 'bottom':    [0.970874], 'top': [76.699029]
        }.items():
            assert_allclose(source[i], j,  rtol = 5e-1, atol = 5e-1)

        cache   = _change(tpe, yaxis = 'hybridisationrate', xaxis = ['track', 'status'])
        factors = [(i, j, k.replace('\u2063', '')) for i, j, k in cache['x_range']['factors']]
        if tpe:
            assert factors == list(zip(repeat(''), repeat(''), ['baseline', 'blockage']))
        else:
            assert factors == list(zip(
                repeat(''), repeat(''), ['baseline', 'identified', 'missing', 'unidentified']
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

def test_statsplot_info_hpins(diskcaching, tmp_path):
    "test the view"
    fov, mdl = _Fig.create(beads = list(range(5)),     withhp = True)
    _Fig.newtasks(mdl, beads = list(range(5, 10)), withhp = True)

    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    _export(fov, tmp_path)

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
        ('\u2063baseline', '', ''),
        ('\u2063\u2063identified', '', ''),
        ('\u2063\u2063\u2063\u2063unidentified', '', ''),
    ]

    cache = _change(yaxis = 'bead', xaxis = ['hairpin'])
    assert cache['yaxis']['axis_label'] == "count (%)"
    assert cache['x_range']['factors'] == list(zip(
        ['GF1', 'GF4', 'GF2', 'GF3'], repeat(""), repeat(""),
    ))

    mdl.display.hairpins = {'GF2', 'GF3'}
    cache = _change()
    assert cache['yaxis']['axis_label'] == "count (%)"
    assert cache['x_range']['factors'] == list(zip(['GF1', 'GF4'], repeat(""), repeat("")))

    mdl.display.hairpins = {}
    cache = _change(yaxis = "distance", xaxis = ["closest"])
    assert cache['yaxis']['axis_label'] == "Δ(closest binding - blockage) (bp)"
    assert cache['x_range']['factors'] == list(zip(
        [
            '38.0', '46.0', '151.0', '157.0', '222.0', '258.0', '274.0', '294.0',
            '347.0', '357.0', '379.0', '393.0', '503.0', '540.0', '569.0', '576.0',
            '659.0', '704.0', '738.0', '754.0', '784.0', '791.0', '795.0', '800.0'
        ],
        repeat(""), repeat(""),
    ))

    mdl.display.hairpins = {'GF2', 'GF3'}
    cache = _change(yaxis = "distance", xaxis = ["hairpin", "closest"])
    assert cache['yaxis']['axis_label'] == "Δ(closest binding - blockage) (bp)"
    assert cache['x_range']['factors'] == [
        ('GF4', '', '38.0'),  ('GF4', '', '294.0'), ('GF4', '', '347.0'), ('GF4', '', '569.0'),
        ('GF4', '', '738.0'), ('GF4', '', '791.0'),
        ('GF1', '', '157.0'), ('GF1', '', '258.0'), ('GF1', '', '393.0'), ('GF1', '', '503.0'),
        ('GF1', '', '704.0'), ('GF1', '', '795.0'),
    ]

    mdl.display.hairpins = {'GF2', 'GF3', 'GF4'}
    cache = _change(yaxis = "bead", xaxis = ["closest", "orientation"])
    assert cache['yaxis']['axis_label'] == 'count (%)'
    assert cache['x_range']['factors'] == [
        ('157.0', '', '+'), ('258.0', '', '+'),     ('393.0', '', '\u2063-'),
        ('503.0', '','\u2063-'), ('704.0', '', '+'), ('795.0', '', '\u2063-')
    ]

    cache = _change(yaxis = "bead", xaxis = ["orientation", "closest"])
    assert cache['yaxis']['axis_label'] == 'count (%)'
    assert cache['x_range']['factors'] == [
        ('+', '', '157.0'), ('+', '', '258.0'), ('+', '', '704.0'),
        ('\u2063-', '', '393.0'), ('\u2063-', '', '503.0'), ('\u2063-', '', '795.0')
    ]

    cache = _change(yaxis = "fn", xaxis = ["hairpin"])
    assert cache['yaxis']['axis_label'] == 'missing (% bindings)'
    assert cache['x_range']['factors'] == [('GF1', '', '')]

    cache = _change(yaxis = "fnperbp", xaxis = ["orientation"])
    assert cache['yaxis']['axis_label'] == 'missing (bp⁻¹)'
    assert cache['x_range']['factors'] == [('+', '', ''), ('\u2063-', '', '')]

def test_statsplot_info_reftrack(diskcaching):
    "test the view"
    fov, mdl = _Fig.create(beads = list(range(5)),     withhp = True)
    _Fig.newtasks(mdl, beads = list(range(5, 10)), withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    mdl.theme.xinfo = [AxisConfig('track')]
    mdl.theme.yaxis = 'hybridisationrate'
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    data  = cache['_stats']['data']
    assert list(data['x']) == [('track 0', '', ''), ('track 1', '', '')]

    mdl.display.reference = next(iter(mdl.tasks.roots))
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    data2 = cache['_stats']['data']
    assert np.isnan(data2['boxcenter']) == 1
    assert len(data2['boxcenter']) == 1
    assert list(data2['x']) == [('', '', '')]

    fov, mdl = _Fig.create(beads = list(range(5)),     withhp = True)
    _Fig.newtasks(mdl, beads = list(range(1, 6)), withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    mdl.theme.yaxis = 'hybridisationrate'
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    data  = cache['_stats']['data']
    assert list(data['x']) == [('track 0', '', ''), ('track 1', '', '')]

    wdg1 = PeakcallingPlotModel(mdl)
    assert wdg1.reftrack == 0

    mdl.display.reference = next(iter(mdl.tasks.roots))

    wdg2 = PeakcallingPlotModel(mdl)
    assert wdg2.reftrack == 1
    assert wdg2.diff(PeakcallingPlotModel(mdl), mdl) == dict(theme = {}, display = {})
    assert wdg2.diff(wdg1, mdl) == dict(theme = {}, display = dict(reference = None))
    assert wdg1.diff(wdg2, mdl) == dict(
        theme = {}, display = dict(reference = next(iter(mdl.tasks.roots)))
    )

    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    data2 = cache['_stats']['data']
    assert_allclose(data2['boxcenter'], [0.])
    assert list(data2['x']) == [('', '', '')]

def test_statsplot_info_fnperbp(diskcaching):
    "test the view"
    fov, mdl = _Fig.create(beads = [1, 7, 14, 33, 12], withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    mdl.theme.__dict__.update(
        xinfo = [AxisConfig("hairpin"), AxisConfig("closest")],
        yaxis = "fnperbp"
    )
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    assert cache['x_range']['factors'] == list(zip(
        repeat('GF1'), repeat(""), ['157.0', '258.0', '393.0', '503.0', '704.0', '795.0']
    ))

    stats = cache['_stats']['data']
    for i in ('bottom', 'top'):
        assert np.isnan(stats[i]).sum() == 0

    assert np.all(stats['bottom'] <= stats['boxcenter'])
    assert np.all(stats['top']    >= stats['boxcenter'])

def test_statsplot_info_filter(diskcaching):
    "test the view"
    beads, mdl = _Fig.create(beads = [1, 7, 14, 33, 12], withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    mdl.theme.__dict__.update(
        xinfo = [AxisConfig("hairpin"), AxisConfig("closest")],
        yaxis = "fnperbp"
    )

    cache = dict(_HairpinPlot(beads, mdl.tasks.processors)._reset())
    assert cache['x_range']['factors'] == list(zip(
        repeat('GF1'), repeat(""), ['157.0', '258.0', '393.0', '503.0', '704.0', '795.0']
    ))

    mdl.display.ranges[('peaks', 'baseposition')] = Slice(200, 400)
    cache = dict(_HairpinPlot(beads, mdl.tasks.processors)._reset())
    assert cache['x_range']['factors'] == list(zip(
        repeat('GF1'), repeat(""), ['258.0', '393.0']
    ))

def test_statsplot_info_pkcount(diskcaching):
    "test the view"
    beads, mdl = _Fig.create(beads = [13, 3, 27], withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    for name in ('closest', 'exclusive'):
        mdl.theme.__dict__.update(
            xinfo = [AxisConfig("hairpin"), AxisConfig(name)],
            yaxis = "bead"
        )

        cache = dict(_HairpinPlot(beads, mdl.tasks.processors)._reset())
        assert_allclose(cache['_stats']['data']['boxheight'], [100.,  *((200/3,)*3), *((100,)*3)])
        assert cache['x_range']['factors'] == [
            ('GF3', '', '46.0'), ('GF3', '', '274.0'), ('GF3', '', '357.0'),
            ('GF3', '', '576.0'), ('GF3', '', '659.0'), ('GF3', '', '754.0'),
            ('GF3', '', '784.0')
        ]

def test_statsplot_info_hpins1(diskcaching):
    "test the view"
    fov, mdl = _Fig.create(withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))
    mdl.theme.__dict__.update(xinfo = [AxisConfig("status")], yaxis = "averageduration")
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    _check_validity(cache, "binding duration (s)")
    assert cache['x_range']['factors'] == [
        ('\u2063baseline', '', ''),
        ('\u2063\u2063identified', '', ''),
        ('\u2063\u2063\u2063\u2063unidentified', '', ''),
    ]

def test_statsplot_info_hpins3(diskcaching):
    "test the view"
    fov, mdl = _Fig.create(withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))
    mdl.theme.__dict__.update(xinfo = [AxisConfig("closest")], yaxis = "distance")
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    _check_validity(cache, "Δ(closest binding - blockage) (bp)")
    assert cache['x_range']['factors'] == list(zip(
        [
            '38.0', '46.0', '151.0', '157.0', '222.0', '258.0', '274.0', '294.0',
            '347.0', '357.0', '379.0', '393.0', '503.0', '540.0', '569.0', '576.0',
            '659.0', '704.0', '738.0', '754.0', '784.0', '791.0', '795.0', '800.0'
        ],
        repeat(""), repeat(""),
    ))

def test_statsplot_info_binned(diskcaching):
    "test the view"
    fov, mdl = _Fig.create(withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))
    mdl.theme.__dict__.update(xinfo = [AxisConfig("binnedz")], yaxis = "distance")
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    _check_validity(cache, "Δ(closest binding - blockage) (bp)")
    vals = [float(i[0]) for i in cache['x_range']['factors']]
    assert_allclose(vals, np.round(vals, 2))
    assert_allclose(np.diff(vals), np.round(np.diff(vals), 1))
    assert .001 <= vals[0] <= .1

    mdl.theme.__dict__.update(xinfo = [AxisConfig("binnedbp")], yaxis = "distance")
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    _check_validity(cache, "Δ(closest binding - blockage) (bp)")

    assert all(i[0].endswith(".0") for i in cache['x_range']['factors'])
    vals = [float(i[0]) for i in cache['x_range']['factors']]
    assert_allclose(vals, np.round(vals))
    assert_allclose(np.diff(vals), np.round(np.diff(vals)))
    assert 20 <= vals[0] <= 50

    fov._fig.__dict__['x_range'] = Range1d()
    mdl.theme.linear = True
    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    assert fov._fig.x_range in cache
    assert 'start' in cache[fov._fig.x_range]
    assert cache[_Fig.renderers[0].glyph]['width'] == 5.

def test_statsplot_info_zmum_vsbp(diskcaching):
    "test the view"
    fov, mdl = _Fig.create(withhp = True)
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))
    mdl.theme.__dict__.update(
        xinfo = [AxisConfig("closest"), AxisConfig("binnedz")],
        yaxis = "baseposition"
    )

    cache = dict(_HairpinPlot(fov, mdl.tasks.processors)._reset())
    _check_validity(cache, "z (bp)")
    assert cache['x_range']['factors'] == [
        ('38.0', '', '0.03'), ('46.0', '', '-0.07'), ('46.0', '', '0.03'),
        ('151.0', '', '0.13'), ('157.0', '', '0.03'), ('157.0', '', '0.13'),
        ('222.0', '', '0.13'), ('258.0', '', '0.13'), ('258.0', '', '0.23'),
        ('274.0', '', '0.13'), ('274.0', '', '0.23'), ('294.0', '', '0.13'),
        ('294.0', '', '0.23'), ('347.0', '', '0.23'), ('357.0', '', '0.23'),
        ('357.0', '', '0.33'), ('379.0', '', '0.33'), ('393.0', '', '0.23'),
        ('393.0', '', '0.33'), ('503.0', '', '0.33'), ('503.0', '', '0.43'),
        ('540.0', '', '0.43'), ('569.0', '', '0.43'), ('576.0', '', '0.43'),
        ('576.0', '', '0.53'), ('631.0', '', '0.53'), ('659.0', '', '0.53'),
        ('704.0', '', '0.53'), ('704.0', '', '0.63'), ('738.0', '', '0.53'),
        ('738.0', '', '0.63'), ('754.0', '', '0.63'), ('784.0', '', '0.63'),
        ('784.0', '', '0.73'), ('791.0', '', '0.63'), ('795.0', '', '0.53'),
        ('795.0', '', '0.63'), ('800.0', '', '0.73')
    ]

@integrationmark
def test_statsplot_view_simple(pkviewserver):
    "test the view"

    def _change(rendered = True, xaxis = None, **kwa):
        if xaxis:
            kwa['xinfo'] = [AxisConfig(i) for i in xaxis]
        server.cmd(
            lambda: server.ctrl.theme.update('peakcalling.view.stats', **kwa),
            rendered = rendered
        )

    def _checkbsfact(tpe: bool):
        factors = [(i, j, k.replace('\u2063', '')) for i, j, k in fig.x_range.factors]
        vals    = ['ok', '% good', 'non-closing', 'Δz', 'σ[HF]', '∑|dz|']
        if not tpe:
            vals.insert(4, 'no blockages')
        assert set(factors) == set(zip(
            repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
            repeat(""),
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
        factors = [(i, j, k.replace('\u2063', '')) for i, j, k in fig.x_range.factors]
        if tpe:
            assert factors == list(zip(
                repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
                repeat(""),
                ['baseline', 'blockage']
            ))
        else:
            assert factors == list(zip(
                repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
                repeat(""),
                ['baseline', 'identified', 'missing', 'unidentified']
            ))

        _change(xaxis = ['track', 'beadstatus'], yaxis = 'bead', rendered = True)
        _checkbsfact(tpe)

    server, fig = pkviewserver()
    _check(True)
    server.addhp()
    _check(False)

@integrationmark
def test_statsplot_view_peaks1(pkviewserver):
    "test the view"
    server, fig = pkviewserver(evt = True)

    def _cmd():
        bdctrl = DataSelectionBeadController(server.ctrl)
        avail  = list(bdctrl.availablebeads)
        with server.ctrl.action:
            bdctrl.setdiscarded(server.ctrl, set(avail[5:]))

    server.cmd(_cmd, rendered = pkviewserver.EVT)

    def _cmd2():
        bdctrl = DataSelectionBeadController(server.ctrl)
        avail  = list(bdctrl.availablebeads)
        with server.ctrl.action:
            bdctrl.setdiscarded(server.ctrl, set(avail[:5]+avail[10:]))

    server.load('big_legacy', rendered = True)
    server.cmd(_cmd2, rendered = pkviewserver.EVT)

    _check_validity(fig)
    assert fig.x_range.factors == [
        ('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', '\u2063% good'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', '\u2063non-closing'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', '\u2063∑|dz|')
    ]

    modal = server.selenium.modal("//span[@class='icon-dpx-stats-bars']", True)
    with modal:
        modal.tab("Bead Status")
        for i in (5, 6):  # '% good', 'non-closing'
            modal[f'//input[@name="beadstatustag[{i}]"]'] = "bad"
    server.wait()
    _check_validity(fig)
    assert fig.x_range.factors == [
        ('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', 'ok'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', '\u2063bad'),
        ('1-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec', '', '\u2063∑|dz|')
    ]

    with modal:
        modal.select("//select[@name='xinfo[0].name']", "tracktag")
    server.wait()
    _check_validity(fig)
    assert fig.x_range.factors == [
        ('none', '', 'ok'), ('none', '', '\u2063bad'), ('none', '', '\u2063∑|dz|')
    ]

    with modal:
        modal.select("//select[@name='xinfo[0].name']", "status")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='yaxis']", "averageduration")
    server.wait()

    assert fig.x_range.factors == [
        ('\u2063baseline', '', ''),
        ('\u2063\u2063\u2063\u2063\u2063blockage', '', '')
    ]
    _check_validity(fig, "binding duration (s)")

    server.addhp()
    _check_validity(fig, "binding duration (s)")
    assert fig.x_range.factors == [
        ('\u2063baseline', '', ''),
        ('\u2063\u2063identified', '', ''),
        ('\u2063\u2063\u2063\u2063unidentified', '', ''),
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

    _check_validity(fig)
    assert set(fig.x_range.factors) == {('aaa', '', ''), ('bbb', '', '')}
    assert fig.extra_x_ranges['beadcount'].factors == [('', '', '5'), ('\u2063', '', '2\u2063')]

    with modal:
        modal.tab("Tracks")
        modal["//input[@name='beadmask[0]']"] = "0, 1"
    server.wait()

    _check_validity(fig)
    assert set(fig.x_range.factors) == {('aaa', '', ''), ('bbb', '', '')}
    assert fig.extra_x_ranges['beadcount'].factors == [("", "", '3'), ("\u2063", "", '2\u2063')]

@integrationmark
def test_statsplot_view_hpins2(fovstatshairpin):
    "test the view"
    server, fig, modal = fovstatshairpin
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "hairpin")
        modal.select("//select[@name='yaxis']", "bead")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
    server.wait()

    _check_validity(fig)
    assert fig.x_range.factors == list(zip(
        ['GF4', 'GF1', 'GF2', 'GF3'], repeat(""), repeat(""),
    ))

    with modal:
        modal.tab("Hairpins")
        for i in (2, 3):
            modal.driver.execute_script(
                f"arguments[0].removeAttribute('checked')",
                modal[f"//input[@name='hairpinsel[{i}]']"]
            )
    server.wait()

    _check_validity(fig)
    assert fig.x_range.factors == list(zip(['GF4', 'GF1'], repeat(""), repeat("")))

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

    _check_validity(fig)
    assert fig.x_range.factors == [
        ('157.0', '', '+'), ('258.0', '', '+'), ('393.0', '', '\u2063-'),
        ('503.0', '', '\u2063-'), ('704.0', '', '+'), ('795.0', '', '\u2063-')
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
    _check_validity(fig)
    assert fig.x_range.factors == [
        ('+', '', '157.0'), ('+', '', '258.0'), ('+', '', '704.0'),
        ('\u2063-', '', '393.0'), ('\u2063-', '', '503.0'), ('\u2063-', '', '795.0')
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
    _check_validity(fig, "missing (% bindings)")
    assert fig.x_range.factors == list(zip(['GF1', 'GF4'], repeat(""), repeat("")))

    with modal:
        modal.select("//select[@name='xinfo[0].name']", "orientation")
        modal.select("//select[@name='xinfo[1].name']", "xxx")
        modal.select("//select[@name='yaxis']", "fnperbp")

    _check_validity(fig, 'missing (bp⁻¹)')
    assert fig.x_range.factors == list(zip(['+', '\u2063-'], repeat(""), repeat("")))

@integrationmark
def test_statsplot_view_hpins7(pkviewserver):
    "test the view"
    server, fig = pkviewserver()
    server.ctrl.theme.model("peakcalling.view.stats").linear = False
    server.addhp()
    modal       = server.selenium.modal("//span[@class='icon-dpx-stats-bars']", True)
    with modal:
        modal.select("//select[@name='xinfo[0].name']", "hairpin")
        modal.select("//select[@name='xinfo[1].name']", "closest")
        modal.select("//select[@name='yaxis']", "fnperbp")
        modal.tab("Hairpins")
        for i in (0, 2, 3, 4):
            modal.driver.execute_script(
                f"arguments[0].removeAttribute('checked')",
                modal[f"//input[@name='hairpinsel[{i}]']"]
            )
    server.wait()
    _check_validity(fig, 'missing (bp⁻¹)')


if __name__ == '__main__':
    from pathlib import Path
    test_statsplot_info_zmum_vsbp(Path("/tmp/dd"))
    from importlib import import_module
    from tests.testingcore.bokehtesting import BokehAction
    with BokehAction(None) as bka:
        test_statsplot_view_hpins7(
            getattr(
                import_module("tests.peakcalling.conftest"), '_server'
            )(bka, Path("/tmp/disk_dir"), "")
        )
