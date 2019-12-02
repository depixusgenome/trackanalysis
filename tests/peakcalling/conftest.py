#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"peakcalling info"
import os
import warnings
from   typing                   import Union
import pytest
from   tests.testingcore        import path as utpath
from   peakcalling.model        import DiskCacheConfig, JobModel

_EVT  = 'peakcalling.view.jobs.stop'

@pytest.fixture(scope="session")
def cache_dir(tmpdir_factory):
    "creates a session-wide position for the diskcache"
    return tmpdir_factory.mktemp("diskcache_dir")

@pytest.fixture()
def diskcaching(cache_dir, monkeypatch):
    "recalls previously cached analyses and stores new ones"
    return _diskcache(cache_dir, monkeypatch)

@pytest.fixture
def pkviewserver(bokehaction, cache_dir, request):
    "creates a factory for the basic server"
    return _server(bokehaction, cache_dir, request)

@pytest.fixture
def fovstatspeaks(bokehaction, cache_dir, request):
    "creates a server with 2 fovs"
    return _fovstatspeaks(bokehaction, cache_dir, request)

@pytest.fixture
def fovstatshairpin(bokehaction, cache_dir, request):
    "creates a server with 2 fovs"
    return _fovstatshairpin(bokehaction, cache_dir, request)

def _diskcache(cache_dir, monkeypatch):
    cnf = DiskCacheConfig(path = str(cache_dir))
    cnf.clear()
    old = JobModel.launch

    def _launch(self, processors, emitter = None, **_):
        cnf.update(processors)
        old(self, processors, emitter)
        cnf.insert(processors)

    monkeypatch.setattr(JobModel, 'launch', _launch)

def _server(bokehaction, cache_dir, request):
    # pylint: disable=protected-access,import-outside-toplevel

    class _ServerFactory:
        DEFAULT = 'BeadsScatterPlot' if (
            (isinstance(request, str) and 'beadsplot' in request)
            or (
                hasattr(request, 'function')
                and (
                    'beadsplot' in request.function.__name__
                    or  'beadsplot' in request.function.__module__
                )
            )
        ) else 'FoVStatsPlot'
        EVT     = _EVT

        def __call__(self, viewname: str = "", evt: Union[str, bool] = _EVT):
            if not viewname:
                viewname = self.DEFAULT
            filters = [
                (FutureWarning,      ".*elementwise comparison failed;.*"),
                (RuntimeWarning,     ".*All-NaN slice encountered.*"),
                (DeprecationWarning, ".*elementwise comparison failed;.*"),
                (DeprecationWarning, '.*Using or importing the ABCs from.*'),
                (DeprecationWarning, '.*the html argument of XMLParser.*'),
                (DeprecationWarning, '.*defusedxml.lxml is no longer supported and .*'),
            ]

            with warnings.catch_warnings():
                for ix1, ix2 in filters:
                    warnings.filterwarnings('ignore', category = ix1, message = ix2)
                import hybridstat.view._io  # noqa  # pylint: disable=unused-import

            server = bokehaction.start(
                f'peakcalling.view.{viewname}',
                'taskapp.toolbar',
                filters = filters,
                runtime = 'selenium'
            )

            server.ctrl.theme.model("peakcalling.diskcache").path = str(cache_dir)

            for i in ('beads', 'stats'):
                if f'peakcalling.view.{i}' in server.ctrl.theme:
                    server.ctrl.theme.model(f'peakcalling.view.{i}').tracknames = "full"

            server.ctrl.theme.model("peakcalling.precomputations").multiprocess = (
                'TEAMCITY_PROJECT_NAME' not in os.environ
            )

            fig = getattr(getattr(server.view.views[0], '_mainview'), '_fig')
            server.load('big_legacy', rendered = evt)

            server.addhp = lambda: self.addhp(server)
            return server, fig

        @staticmethod
        def addhp(server):
            "add the hairpin"
            from   peakcalling.processor    import FitToHairpinTask
            server.cmd(
                lambda: server.ctrl.tasks.addtask(
                    next(next(server.ctrl.tasks.tasklist(...))),
                    FitToHairpinTask(sequences = utpath("hairpins.fasta"), oligos = "kmer")
                ),
                rendered = _EVT
            )

    return _ServerFactory()

def _fovstatspeaks(bokehaction, cache_dir, request):
    "creates a server with 2 fovs"
    from   taskcontrol.beadscontrol import DataSelectionBeadController
    server, fig = _server(bokehaction, cache_dir, request)('FoVStatsPlot', evt = True)
    server.ctrl.theme.model("peakcalling.view.stats").linear = False

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

    modal = server.selenium.modal("//span[@class='icon-dpx-stats-bars']", True)

    return (server, fig, modal)

def _fovstatshairpin(bokehaction, cache_dir, request):
    "creates a server with 2 fovs"
    server, fig, modal = _fovstatspeaks(bokehaction, cache_dir, request)
    server.addhp()
    return server, fig, modal
