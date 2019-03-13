#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Testing anastore"
from   typing           import cast
import warnings
import sys
import numpy

import taskstore as anastore
import anastore.api
from anastore           import modifyclasses, TPE, DELETE, RESET
from tests.testingcore  import path as _utpath, Path
from taskmodel.track    import TrackReaderTask, CycleCreatorTask
from taskmodel.tagging  import TaggingTask

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

    monkeypatch.setattr(anastore.api, 'PATCHES', {'tasks': patch})
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

def test_storetype():
    u"tests storing arrays"
    vals = dict(a = TaggingTask, b = [TaggingTask])
    loaded = anastore.loads(anastore.dumps(vals))
    assert set(vals.keys()) == set(loaded.keys()) # pylint: disable=no-member
    assert vals['a'] is TaggingTask
    assert vals['b'][0] is TaggingTask

def test_modifyclass():
    "tests class modifications"
    val = [{TPE: 'toto'}, {TPE: 'titi', 'attr': 1}]
    modifyclasses(val, 'toto', DELETE, 'titi', RESET)
    assert val == [{TPE: 'titi'}]

    val = {'a':{TPE: 'toto'}, 'b': {TPE: 'titi', 'attr': 1}}
    modifyclasses(val, 'toto', DELETE, 'titi', RESET)
    assert val == {'b': {TPE: 'titi'}}

    val = [{'a':{TPE: 'toto', 'delete': 1, 'change': 2, 'reset' : 3, 'reset2': 4}}]
    modifyclasses(val, 'titi', dict(), 'toto',
                  dict(delete   = DELETE,
                       reset    = RESET,
                       reset2   = lambda x: RESET,
                       delete2  = lambda x: DELETE,
                       change   = lambda x: x*2,
                       __name__ = 'tata'))
    assert val == [{'a': {TPE: 'tata', 'change': 4}}]

    val = [{'a':{TPE: 'toto', 'attr': 1}}]
    modifyclasses(val, 'toto', dict(attr = 'newname'),
                  'toto', dict(newname = lambda x: x*2))
    assert val == [{'a': {TPE: 'toto', 'newname': 2}}]

def test_file():
    "tests a ana file"
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category = DeprecationWarning,
                                message  = '.*the imp module is .*')
        for i in Path(cast(str, _utpath())).glob("*.ana"):
            assert anastore.load(i) is not None
        assert anastore.load(_utpath("reportv2.xlsx"), fromxlsx = True) is not None

if __name__ == '__main__':
    test_file()
