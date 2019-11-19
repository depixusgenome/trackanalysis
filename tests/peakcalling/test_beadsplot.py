#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=unused-argument
"peakcalling beadsplot tests"
from   itertools                import repeat
import numpy as np
from   numpy.testing            import assert_equal
from   tests.testutils          import integrationmark
from   tests.testingcore        import path as utpath
from   cleaning.processor       import DataCleaningTask, ClippingTask
from   eventdetection.processor import ExtremumAlignmentTask, EventDetectionTask
from   peakfinding.processor    import PeakSelectorTask
from   peakcalling.processor    import FitToHairpinTask
from   peakcalling.model        import Slice
from   peakcalling.view._beadsplot import (     # pylint: disable=protected-access
    BeadsScatterPlot, _HairpinPlot, _PeaksPlot
)
from   taskmodel.track          import TrackReaderTask, DataSelectionTask
from   taskcontrol.taskcontrol  import create

class _Fig:
    extra_x_ranges = {'beadcount': 'beadcount'}
    x_range        = 'x_range'
    y_range        = type('y_range', (), {'start': 0, 'end': 1})
    yaxis          = ['yaxis']
    xaxis          = ['xaxistop', 'xaxisbottom']

    class _CData:
        def __init__(self, data):
            self.data = data

    @classmethod
    def create(cls, **kwa):
        "patch BeadsScatterPlot to get rid of Bokeh objects"
        fov = BeadsScatterPlot()
        setattr(fov, '_fig',     cls())
        setattr(fov, '_expdata', '_expdata')
        setattr(fov, '_theodata', cls._CData(dict(
            {i: [''] for i in  ('hairpin', 'status', 'color')},
            bindingposition = [0],
            x               = [('track1', '0')]
        )))
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

def test_beadsplot_info_simple(diskcaching):
    "test the view"
    # pylint: disable=protected-access
    beads, mdl = _Fig.create()

    # testing for when there is nothing to plot
    for cls in _PeaksPlot, _HairpinPlot:
        assert (
            dict(cls(beads, mdl.tasks.processors)._reset())['x_range']['factors']
            == [('track1', '0')]
        )

    def _change(tpe, **kwa):
        mdl.theme.__dict__.update(**kwa)
        cls = _PeaksPlot if tpe else _HairpinPlot
        return dict(cls(beads, mdl.tasks.processors)._reset())

    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    cache = _change(True)
    assert cache['x_range']['factors'] == list(zip(
        repeat(''), repeat(''),
        [
            '0', '1', '2', '3', '4', '7', '8', '12', '13', '14', '17', '18', '23',
            '24', '25', '27', '33', '34', '35', '37'
        ]
    ))

    next(iter(mdl.tasks.tasks.tasks.tasks.values())).add(
        FitToHairpinTask(
            sequence = utpath("hairpins.fasta"),
            oligos   = "4mer",
        ),
        mdl.tasks.tasks.state.processors[FitToHairpinTask]
    )
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    cache = _change(False)
    assert cache['x_range']['factors'] == [
        ('GF1', '', '14'), ('GF1', '', '33'), ('GF1', '', '1'), ('GF1', '', '7'),
        ('GF1', '', '25'), ('GF1', '', '35'), ('GF1', '', '12'), ('GF3', '', '27'),
        ('GF3', '', '13'), ('GF3', '', '3'), ('GF3', '', '17'), ('GF3', '', '37'),
        ('GF3', '', '23'), ('GF3', '', '18'), ('GF4', '', '34'), ('GF4', '', '0'),
        ('GF4', '', '4'), ('GF4', '', '24'), ('GF2', '', '2')
    ]

    mdl.display.hairpins = {'015', 'GF2', 'GF3', 'GF4'}
    cache = _change(False)
    assert cache['x_range']['factors'] == [
        ('GF1', '', '14'), ('GF1', '', '33'), ('GF1', '', '1'), ('GF1', '', '7'),
        ('GF1', '', '25'), ('GF1', '', '35'), ('GF1', '', '12')
    ]

def test_beadsplot_info_filter(diskcaching):
    "test the view"
    # pylint: disable=protected-access
    beads, mdl = _Fig.create()
    next(iter(mdl.tasks.tasks.tasks.tasks.values())).add(
        FitToHairpinTask(
            sequence = utpath("hairpins.fasta"),
            oligos   = "4mer",
        ),
        mdl.tasks.tasks.state.processors[FitToHairpinTask]
    )
    mdl.tasks.jobs.launch(list(mdl.tasks.processors.values()))

    cache = dict(_HairpinPlot(beads, mdl.tasks.processors)._reset())
    arr = cache['_expdata']['data']['closest']
    arr = np.unique(arr[np.isfinite(arr)])
    assert_equal(
        arr,
        [
            38.,  46., 151., 157., 222., 258., 274., 294., 347., 357., 379., 393., 503.,
            540., 569., 576., 631., 659., 704., 738., 754., 784., 791., 795., 800.
        ]
    )

    arr = np.unique(
        next(j for i,j in cache.items() if isinstance(i, _Fig._CData))
        ['data']['bindingposition']
    )
    assert_equal(
        arr,
        [
            38.,  46., 151., 157., 222., 258., 274., 294., 347., 357., 379., 393., 503.,
            540., 569., 576., 631., 659., 704., 738., 754., 784., 791., 795., 800.
        ]
    )

    mdl.display.ranges[('peaks', 'baseposition')] = Slice(100, 400)
    cache = dict(_HairpinPlot(beads, mdl.tasks.processors)._reset())
    arr = cache['_expdata']['data']['closest']
    arr = np.unique(arr[np.isfinite(arr)])
    assert_equal(arr, [151., 157., 222., 258., 274., 294., 347., 357., 379., 393.])

    arr = np.unique(
        next(j for i,j in cache.items() if isinstance(i, _Fig._CData))
        ['data']['bindingposition']
    )
    assert_equal(arr, [151., 157., 222., 258., 274., 294., 347., 357., 379., 393.])

@integrationmark
def test_beadsplot_view(pkviewserver):
    "test the view"
    server, fig = pkviewserver()

    assert fig.x_range.factors == list(zip(
        repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
        repeat(''),
        [
            '0', '1', '2', '3', '4', '7', '8', '12', '13', '14', '17', '18', '23',
            '24', '25', '27', '33', '34', '35', '37'
        ]
    ))

    server.addhp()

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
