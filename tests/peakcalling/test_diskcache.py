#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring,protected-access
"testing peakcalling DiskCache"
from pathlib import Path
from peakcalling.view._model._diskcache  import DiskCacheConfig, VERSION, VERSION_KEY, DiskCache
from taskcontrol.taskcontrol        import create
from taskmodel.track                import UndersamplingTask, TrackReaderTask
from taskmodel.dataframe            import DataFrameTask
from tests.testingcore              import path as utpath

def test_diskcache_insert(tmp_path):
    reader = TrackReaderTask(path = utpath("big_legacy"))
    tasks  = [
        create(reader, UndersamplingTask(), DataFrameTask()),
        create(reader, DataFrameTask())
    ]
    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': i})

    cnf = DiskCacheConfig(path = str(tmp_path/"cache"))
    cnf.clear()
    cnf.insert(tasks, 10001)
    assert cnf.get(tasks[0], 10001)['index'] == 0
    assert cnf.get(tasks[1], 10001)['index'] == 1

    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': i*2+1})

    cnf.insert(tasks, 10002)
    assert cnf.get(tasks[0], 10002)['index'] == 1
    assert cnf.get(tasks[1], 10002)['index'] == 3

    tasks  = [
        create(reader, UndersamplingTask(), DataFrameTask()),
        create(reader, DataFrameTask())
    ]
    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': -1})

    cnf.update(tasks, 10001)
    assert tasks[0].data.getcache(DataFrameTask)()['index'] == -1
    assert tasks[1].data.getcache(DataFrameTask)()['index'] == -1

    cnf.update(tasks, 10002)
    assert tasks[0].data.getcache(DataFrameTask)()['index'] == 1
    assert tasks[1].data.getcache(DataFrameTask)()['index'] == 3

def test_diskcache_clear(tmp_path):
    reader = TrackReaderTask(path = utpath("big_legacy"))
    tasks  = [
        create(reader, UndersamplingTask(), DataFrameTask()),
        create(reader, DataFrameTask())
    ]
    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': i})

    cnf = DiskCacheConfig(path = str(tmp_path/"cache"))
    assert not Path(cnf.path).exists()

    cnf.insert(tasks, 10001)
    assert Path(cnf.path).exists()

    cnf.clear(complete = True)
    with DiskCache(cnf.path) as cache:
        assert sum(1 for _ in cache.iterkeys()) == 1
        assert cache.get(VERSION_KEY) == VERSION

    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': -1})
    cnf.insert(tasks, 10001)
    assert Path(cnf.path).exists()

    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': -2})
    cnf.update(tasks, 10001)
    assert tasks[0].data.getcache(DataFrameTask)()['index'] == -1
    assert tasks[1].data.getcache(DataFrameTask)()['index'] == -1

    for i, procs in enumerate(tasks):
        procs.data.setcache(DataFrameTask, {'index': -2})
    cnf.clear(processors = tasks)
    assert Path(cnf.path).exists()
    cnf.update(tasks, 10001)
    assert tasks[0].data.getcache(DataFrameTask)()['index'] == -2
    assert tasks[1].data.getcache(DataFrameTask)()['index'] == -2


if __name__ == '__main__':
    from shutil  import rmtree
    rmtree(Path("/tmp/discache"), ignore_errors = True)
    test_diskcache_insert(Path("/tmp/discache"))
    rmtree(Path("/tmp/discache"), ignore_errors = True)
