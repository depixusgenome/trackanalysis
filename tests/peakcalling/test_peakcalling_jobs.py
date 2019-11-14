#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring,protected-access
"testing peakcalling JOBS"
import asyncio
from time                           import sleep, time
from multiprocessing                import current_process

from peakcalling.view._model._jobs  import _JobRunner as JobRunner, JobModel
from peakcalling.view._model._tasks import TasksModel, _RootCache
from taskcontrol.taskcontrol        import ProcessorController
from taskcontrol.processor.track    import TrackReaderProcessor
from taskmodel.track                import TrackReaderTask
from taskmodel.dataframe            import DataFrameTask
from taskmodel.processors           import appendtask
from tests.testingcore              import path as utpath

class _Cache:
    def __init__(self, vals, cache):
        self.info  = vals
        self.cache = cache

    def setcachedefault(self, *_):
        return self.cache

    def getcache(self, *_):
        return lambda: self.cache

    def keys(self):
        return self.info.keys()

    def __getitem__(self, i):
        sleep(0.02)
        return current_process().pid, time()

class _Track:
    path = "path"

class _Proc:
    def __init__(self, info, cache):
        self.data  = _Cache(info, cache)
        self.model = [_Track]

    def cleancopy(self):
        return self

    def run(self):
        yield self.data


MDL  = JobModel()
MDL.config.ncpu = 2
MDL.config.maxkeysperjob = 10
JOBS = JobRunner(MDL)


def test_peakcalling_jobs():
    "test peakcalling JOBS"
    procs = [
        _Proc({i: 1 for i in range(21)}, {}),
        _Proc({}, {}),
        _Proc({i: 2 for i in range(21)}, {i: 22 for i in range(21)}),
        _Proc({i: 3 for i in range(21)}, {i: 33 for i in range(10)}),
        _Proc({i: 4 for i in range(21)}, {i: 44 for i in range(10, 21)}),
        _Proc({i: 5 for i in range(21)}, {i: 55 for i in range(10, 15)}),
    ]

    evts = []

    asyncio.set_event_loop(asyncio.new_event_loop())
    asyncio.run(JOBS.run(procs, evts.append, None))

    assert len(evts) >= 4+3+0+0+2+1+2
    for i in range(4):
        assert evts[i]['taskcache'] is procs[2+i]
    assert set(evts[0]['beads']) == set(range(21))
    assert set(evts[1]['beads']) == set(range(10))
    assert set(evts[2]['beads']) == set(range(10, 21))
    assert set(evts[3]['beads']) == set(range(10, 15))
    for i in (0, 3, 4, 5):
        assert set(procs[i].data.cache) == set(range(21))
    assert set(procs[1].data.cache) == set()
    assert set(procs[2].data.cache.values()) == {22}
    assert {i for i, j in procs[3].data.cache.items() if j == 33} == set(range(10))
    assert {i for i, j in procs[5].data.cache.items() if j == 55} == set(range(10, 15))
    for i in (0, 3, 4, 5):
        assert (
            len({i[0] for i in  procs[i].data.cache.values() if  not isinstance(i, int)})
            == 1 + (i in (0, 5))
        )

def test_peakcalling_jobs_cancel1():
    procs = [
        _Proc({i: 1 for i in range(21)}, {}),
        _Proc({i: 2 for i in range(21)}, {})
    ]

    async def _wait():
        await asyncio.sleep(0.3)
        MDL.display.calls += 1

    asyncio.set_event_loop(asyncio.new_event_loop())
    asyncio.get_event_loop().run_until_complete(
        asyncio.gather(_wait(), JOBS.run(procs, (lambda _: None), None))
    )
    assert len(procs[0].data.cache) > 0
    assert len(procs[1].data.cache) == 0

def test_peakcalling_jobs_cancel2():
    "test peakcalling JOBS"
    procs = [
        _Proc({i: 1 for i in range(21)}, {}),
        _Proc({i: 2 for i in range(21)}, {})
    ]
    cache = procs[0].data.cache

    async def _wait():
        await asyncio.sleep(0.2)
        procs[0].data.cache = None

    asyncio.set_event_loop(asyncio.new_event_loop())
    asyncio.get_event_loop().run_until_complete(
        asyncio.gather(_wait(), JOBS.run(procs, (lambda _: None), None))
    )
    assert procs[0].data.cache is None
    assert 0 < len(cache) < 21
    assert len(procs[1].data.cache) == 21


class _Ref:
    def __init__(self):
        self.defaultdata = None

    @staticmethod
    def unique():
        return True

class _DummyProc:
    def __init__(self, task):
        self.task = task

class _Hairpin:
    def __init__(self, resolve = False):
        self.sequences = None
        self.oligos    = None
        self._res      = resolve
        self.fit       = {'aa': 'bb'}

    @staticmethod
    def unique():
        return True

    def resolve(self, _):
        "dummy"
        if not self._res:
            self.oligos = None
            self.fit   = {}
        return self

def test_adapt_procs_ref():
    "test processors adaptor remove ref"

    procs = [ProcessorController() for i in range(3)]
    procs[0].add(TrackReaderTask(utpath("big_legacy")), TrackReaderProcessor)
    procs[0].add(_Ref(), _DummyProc)
    procs[1].add(TrackReaderTask(utpath("big_legacy")), TrackReaderProcessor)
    procs[2].add(TrackReaderTask(utpath("big_legacy")), TrackReaderProcessor)

    mdl = TasksModel()
    mdl.config.defaulttaskindex = lambda *_: appendtask
    for i in (mdl.config.sdi, mdl.config.picotwist):
        i['fittoreference'] = _Ref()
        i['fittohairpin']   = _Hairpin()
        i['dataframe']      = DataFrameTask()

    for i in (_Ref, _Hairpin, DataFrameTask):
        mdl.state.processors[i] = _DummyProc
    mdl.state.processors[TrackReaderTask] = TrackReaderProcessor

    for i in procs:
        mdl.tasks.add(i)
    mdl.dataframes.peaks.measures = {'events': True}

    lst = mdl.processors
    assert len(lst) == len(procs)
    for i in procs:
        assert len(lst[i.model[0]].model) == 3
        assert i.model is not lst[i.model[0]].model
        assert lst[i.model[0]].model[-1].__class__.__name__ == 'DataFrameTask'
        assert lst[i.model[0]].model[-1].measures == {'events': True}

    mdl.state.reference = procs[1].model[0]

    lst = mdl.processors
    assert len(lst) == len(procs)
    for i in procs:
        assert len(lst[i.model[0]].model) == 3 + (i.model[0] is not mdl.state.reference)
        assert i.model is not lst[i.model[0]].model
        assert lst[i.model[0]].model[-1].__class__.__name__ == 'DataFrameTask'
        assert lst[i.model[0]].model[-1].measures == {'events': True}
        if i.model[0] is not mdl.state.reference:
            assert lst[i.model[0]].model[2].__class__.__name__ == '_Ref'
            assert lst[i.model[0]].model[2].defaultdata is lst[mdl.state.reference].data

def test_adapt_procs_fittohp():
    "test processors adaptor remove ref"

    procs = [ProcessorController() for i in range(3)]
    procs[0].add(TrackReaderTask(utpath("big_legacy")), TrackReaderProcessor)
    procs[0].add(_Ref(), _DummyProc)
    procs[0].add(_Hairpin(resolve = True), _DummyProc)
    procs[1].add(TrackReaderTask(utpath("big_legacy")), TrackReaderProcessor)
    procs[2].add(TrackReaderTask(utpath("big_legacy")), TrackReaderProcessor)
    procs[2].add(_Hairpin(resolve = True), _DummyProc)

    mdl = TasksModel()
    mdl.config.defaulttaskindex = lambda *_: appendtask
    mdl.state.sequences = 'a'
    for i in (mdl.config.sdi, mdl.config.picotwist):
        i['fittoreference'] = _Ref()
        i['fittohairpin']   = _Hairpin(resolve = True)
        i['dataframe']      = DataFrameTask()

    for i in (_Ref, _Hairpin, DataFrameTask):
        mdl.state.processors[i] = _DummyProc
    mdl.state.processors[TrackReaderTask] = TrackReaderProcessor

    for i in procs:
        mdl.tasks.add(i)
    mdl.dataframes.fits.measures = {'peaks': {'all': True, 'events': True}}

    lst = mdl.processors
    assert len(lst) == len(procs)
    for i in procs:
        assert len(lst[i.model[0]].model) == 4
        assert i.model is not lst[i.model[0]].model
        assert lst[i.model[0]].model[2].__class__.__name__ == '_Hairpin'
        assert lst[i.model[0]].model[-1].__class__.__name__ == 'DataFrameTask'
        assert lst[i.model[0]].model[-1].measures == {'peaks': {'all': True, 'events': True}}
        assert lst[i.model[0]].model[2].__class__.__name__ == '_Hairpin'
        if i.model[0] in (procs[0].model[0], procs[2].model[0]):
            assert lst[i.model[0]].model[2].sequences is None
        else:
            assert lst[i.model[0]].model[2].sequences == 'a'

    mdl.state.reference = procs[1].model[0]

    lst = mdl.processors
    assert len(lst) == len(procs)
    for i in procs:
        assert len(lst[i.model[0]].model) == 4 + (i.model[0] is not mdl.state.reference)
        assert i.model is not lst[i.model[0]].model
        assert lst[i.model[0]].model[-1].__class__.__name__ == 'DataFrameTask'
        assert lst[i.model[0]].model[-1].measures == {'peaks': {'all': True, 'events': True}}
        assert lst[i.model[0]].model[-2].__class__.__name__ == '_Hairpin'
        if i.model[0] in (procs[0].model[0], procs[2].model[0]):
            assert lst[i.model[0]].model[-2].sequences is None
        else:
            assert lst[i.model[0]].model[-2].sequences == 'a'
        if i.model[0] is not mdl.state.reference:
            assert lst[i.model[0]].model[2].__class__.__name__ == '_Ref'
            assert lst[i.model[0]].model[2].defaultdata is lst[mdl.state.reference].data

    for i in (mdl.config.sdi, mdl.config.picotwist):
        i['fittohairpin']   = _Hairpin(resolve = False)
    lst = mdl.processors
    assert len(lst) == 2

def test_lru():
    tasks = [TrackReaderTask(utpath("big_legacy")), _Ref()]
    lru = _RootCache(2)
    info = {}
    assert info is lru.setdefault(tasks, info)
    assert info is lru.setdefault(tasks, None)
    assert info is lru[tasks]
    assert tasks in lru

    lru[tasks] = cache = {}
    assert tasks in lru
    assert info is not lru[tasks]
    assert cache is lru[tasks]

    tasks = [TrackReaderTask(utpath("big_legacy")), _Ref()]
    assert cache is lru.setdefault(tasks, None)

    tasks2 = [TrackReaderTask(utpath("big_legacy"))]
    assert tasks2 not in lru
    info2  = lru.setdefault(tasks2, None)
    assert info2 is lru.setdefault(tasks2, None)

    tasks3 = [TrackReaderTask(utpath("big_legacy")), _Ref(), _Hairpin()]
    lru.setdefault(tasks3, None)
    assert tasks not in lru
    assert tasks2  in lru

    del lru[tasks2]
    assert tasks2  not in lru


if __name__ == '__main__':
    test_adapt_procs_ref()
