#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Testing anastore"
import sys
import numpy

import anastore
from model.task import TrackReaderTask, CycleCreatorTask, TaggingTask

BEENTHERE = []
class _Toto(TaggingTask):
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.attr = kwa['attr']

    def __getstate__(self):
        BEENTHERE.append(1)
        return tuple(self.__dict__.items())

    def __setstate__(self, args):
        BEENTHERE.append(2)
        self.__dict__.update(self.__class__(**dict(args)).__dict__)

def test_storetasks(monkeypatch):
    u"tests storing tasks"
    monkeypatch.setattr(sys.modules['__main__'], '_Toto', _Toto, False)
    monkeypatch.setattr(sys.modules.get('anastoretest', sys.modules['__main__']),
                        '_Toto', _Toto, False)

    tasks = [TrackReaderTask(path = 'mypath'),
             TaggingTask(level  = 'bead',
                         tags   = {'tag1': {1,2,3}, 'tag3': {4, 5, 6}},
                         action = 'remove'),
             CycleCreatorTask(),
             TaggingTask(level  = 'cycle',
                         tags   = {'tag4': {(1,1),(2,1),(3,1)}},
                         action = 'keep'),
             _Toto(level  = 'peak',
                   tags   = {'tag5': {(1,1),(2,1),(3,1)}},
                   action = 'keep',
                   attr   = 'whatever')]

    used = []
    def _vers(ind):
        def _fcn(val, _ = ind):
            used.append(_)
            return val
        return _fcn

    patch = anastore.Patches()
    for _ in range(5):
        patch.patch(_vers(_))

    monkeypatch.setattr(anastore, '__TASKS__', patch)
    dumped = anastore.dumps(tasks)
    assert dumped[:len('[{"version": 5},')] == '[{"version": 5},'

    for _ in range(5,8):
        patch.patch(_vers(_))

    loaded = anastore.loads(dumped)
    assert used   == list(range(5, 8))
    assert BEENTHERE == [1,2]
    for i, j in zip(loaded, tasks):
        assert i.__dict__ == j.__dict__, str(i)

def test_storenumpy():
    u"tests storing arrays"
    vals = dict(a = numpy.array([None]*5), b = numpy.zeros((200,), dtype = numpy.int8),
                c = numpy.arange(5, dtype = numpy.float32),
                d = numpy.nanmedian)
    loaded = anastore.loads(anastore.dumps(vals))
    assert set(vals.keys()) == set(loaded.keys()) # pylint: disable=no-member
    assert numpy.array_equal(vals['a'], loaded['a'])
    assert numpy.array_equal(vals['b'], loaded['b'])
    assert numpy.array_equal(vals['c'], loaded['c'])
    assert loaded['d'] is numpy.nanmedian

if __name__ == '__main__':
    test_storenumpy()
