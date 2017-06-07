#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring
"Test control"

from concurrent.futures       import ThreadPoolExecutor, ProcessPoolExecutor
from typing                   import List # pylint: disable=unused-import
from itertools                import product
import os
import sys

from model.task               import Task, RootTask, Level
from data.trackitems          import TrackItems
from control.processor        import Processor
from control.processor.runner import Cache, pooledinput, run, poolchunk
from testingcore              import DummyPool

class _RootTask(RootTask):
    pass

class _RootProcessor(Processor):
    CNT  = 0
    @classmethod
    def _run(cls):
        cls.CNT += 1
        data = {i: [(os.getpid(), 'r')] for i in range(3)}
        yield TrackItems(data = data, parents = ('rr',))

    @staticmethod
    def isslow():
        return True

    def run(self, args):
        args.apply(self._run)

class _ATask(Task):
    level = Level.none
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.pool = kwa['pool']
        self.name = kwa['name']

class _AProcessor(Processor):
    DONE_POOL = [] # type: List[str]
    DONE_NORM = [] # type: List[str]
    def canpool(self):
        return self.task.pool

    @classmethod
    def _run(cls, cnf, kwa):
        if cnf['pool']:
            def _fcn(frame):
                data = pooledinput(kwa['pool'], kwa['data'], frame)
                cls.DONE_POOL.append(cnf['name'])
                for j in data.values():
                    j.append((os.getpid(), cnf['name']))
                return data

            return lambda i: i.new().withdata(_fcn)

        def _act(info):
            cls.DONE_NORM.append((cnf['name'], info[0]))
            info[1].append((os.getpid(), cnf['name']))
            return info

        return lambda i: i.withaction(_act)

    def run(self, args):
        args.apply(self._run(self.task.config(), args.poolkwargs(self.task)))

def test_chunk():
    "tests chunks"
    assert poolchunk(tuple(range(1)), 5, 0) == (0,)
    for i in range(1, 5):
        assert poolchunk(tuple(range(1)), 5, i) == tuple()

    for i in range(2):
        assert poolchunk(tuple(range(2)), 5, i) == (i,)
    for i in range(2, 5):
        assert poolchunk(tuple(range(2)), 5, i) == tuple()

    for i in range(5):
        assert poolchunk(tuple(range(5)), 5, i) == (i,)

    assert poolchunk(tuple(range(11)), 5, 0) == (0, 1, 2,)
    assert poolchunk(tuple(range(11)), 5, 1) == (3, 4,)
    assert poolchunk(tuple(range(11)), 5, 2) == (5, 6,)
    assert poolchunk(tuple(range(11)), 5, 3) == (7, 8,)
    assert poolchunk(tuple(range(11)), 5, 4) == (9, 10,)

def test_pooled(monkeypatch):
    "testing pooled processors"
    data = Cache([_RootProcessor(_RootTask()),
                  _AProcessor(_ATask(pool = False, name = 'a')),
                  _AProcessor(_ATask(pool = True,  name = 'b')),
                  _AProcessor(_ATask(pool = False, name = 'c')),
                  _AProcessor(_ATask(pool = True,  name = 'd'))])

    vals = tuple(tuple(i) for i in run(data, pool = DummyPool))
    assert len(vals) == 1
    vals = vals[0]
    assert len(vals) == 3
    assert set(i        for i, _ in vals) == {0, 1, 2}
    assert set(len(i)   for _, i in vals) == {5}
    assert len(set(j[0] for _, i in vals for j in i)) == 1
    assert set(''.join(j[-1] for j in i) for _, i in vals) == {'rabcd'}
    assert _RootProcessor.CNT == 4
    assert _AProcessor.DONE_POOL == ['b', 'd']
    assert _AProcessor.DONE_NORM == list(product('ac', range(3)))


    with ThreadPoolExecutor(2) as pool:
        pool.nworkers = 2
        threaded = tuple(tuple(i) for i in run(data, pool = pool))

    assert len(threaded) == 1
    assert vals == threaded[0]

    patch = lambda i, j: monkeypatch.setattr(sys.modules.get('pooledrunnertest',
                                                             sys.modules['__main__']),
                                             i, j, False)
    patch('_ATask',      _ATask)
    patch('_AProcessor', _AProcessor)
    patch('_RootTask',      _RootTask)
    patch('_RootProcessor', _RootProcessor)

    with ProcessPoolExecutor(2) as pool:
        pool.nworkers = 2
        processed = tuple(tuple(i) for i in run(data, pool = pool))

    assert len(processed) == 1
    processed = processed[0]
    assert len(processed) == 3
    assert len(set(j[0] for _, i in processed for j in i)) == 3
    assert set(''.join(j[-1] for j in i) for _, i in processed) == {'rabcd'}

if __name__ == '__main__':
    from testingcore import getmonkey
    test_pooled(getmonkey())
