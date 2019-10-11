#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"test peakcalling views"
import os
import warnings
from   itertools                import repeat
import pytest
from   peakcalling.processor    import FitToHairpinTask
from   tests.testutils          import integrationmark
from   tests.testingcore        import path as utpath

FILTERS = [
    (FutureWarning,      ".*elementwise comparison failed;.*"),
    (RuntimeWarning,     ".*All-NaN slice encountered.*"),
    (DeprecationWarning, ".*elementwise comparison failed;.*"),
    (DeprecationWarning, '.*Using or importing the ABCs from.*'),
    (DeprecationWarning, '.*the html argument of XMLParser.*'),
    (DeprecationWarning, '.*defusedxml.lxml is no longer supported and .*'),
]

@pytest.mark.skipif(
    'TEAMCITY_PROJECT_NAME' in os.environ,
    reason = "the test can hang when run without displays"
)
@integrationmark
def test_peaksview(bokehaction):
    "test the view"
    # pylint: disable=protected-access,unused-import,import-outside-toplevel
    with warnings.catch_warnings():
        for i, j in FILTERS:
            warnings.filterwarnings('ignore', category = i, message = j)
        import hybridstat.view._io  # noqa
    server = bokehaction.start(
        f'peakcalling.view.BeadsScatterPlot',
        'taskapp.toolbar',
        filters = FILTERS,
        runtime = 'selenium'
    )

    fig = getattr(getattr(server.view.views[0], '_mainview'), '_fig')

    server.load('big_legacy', rendered = 'peakcalling.view.jobs.stop')
    assert fig.x_range.factors == list(zip(
        repeat('0-test035_5HPs_mix_CTGT--4xAc_5nM_25C_10sec'),
        [
            '0', '1', '2', '3', '4', '7', '8', '12', '13', '14', '17', '18', '23',
            '24', '25', '27', '33', '34', '35', '37'
        ]
    ))

    server.cmd(
        lambda: server.ctrl.tasks.addtask(
            next(next(server.ctrl.tasks.tasklist(...))),
            FitToHairpinTask(sequences = utpath("hairpins.fasta"), oligos = "kmer")
        ),
        rendered = 'peakcalling.view.jobs.stop'
    )

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
            'peakcalling.view', hairpins = {'015', 'GF2', 'GF3', 'GF4'}
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


if __name__ == '__main__':
    from tests.testingcore.bokehtesting import BokehAction
    with BokehAction(None) as bka:
        test_peaksview(bka)
