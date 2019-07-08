#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Test control"
# pylint: disable=import-error,missing-docstring
import  numpy
from    data.views                  import Cycles, Beads, TrackView
from    taskcontrol.taskcontrol     import TaskController
from    taskcontrol.processor       import Processor, Cache, Runner
from    taskcontrol.processor.track import UndersamplingProcessor
from    taskcontrol.processor.cache import CacheReplacement
import  taskmodel                   as     tasks

from    tests.testingcore           import path as utpath

def test_task_mutations():
    "testing task control"
    # pylint: disable=unused-variable, too-many-locals,invalid-name
    # pylint: disable=too-many-statements
    def _make(ind, fcn):
        def __init__(self, **kwargs):
            tasks.Task.__init__(self, level = tasks.Level.bead)
            self.toto = kwargs.get('toto', 1)
        def _run(self, args):
            def _xx(frame):
                fcn(self, args.data)
                return frame
            args.gen = iter(_xx(frame) for frame in args.gen)

        dum  = type('_DummyTask%d' % ind, (tasks.Task,),
                    dict(__init__ = __init__, level = tasks.Level.bead))
        proc = type('_DummyProcess%d' % ind, (Processor,),
                    dict(run   = _run, tasktype = dum))
        return dum, proc

    cnt = [0]
    _DummyTask0, _DummyProcess0 = _make(0, lambda i, j: j.setcachedefault(i, list(cnt)))
    _DummyTask1, _DummyProcess1 = _make(1, lambda i, j: None)
    _DummyTask2, _DummyProcess2 = _make(2, lambda i, j: j.setcache(i, list(cnt)))

    ctrl = TaskController()

    events = dict() # type: ignore
    for evt in 'opentrack', 'closetrack', 'addtask', 'removetask', 'updatetask':
        def _obs(*args, name = evt, **kwargs):
            events.setdefault(name, []).append((args, kwargs))
        ctrl.observe(evt, _obs)


    read = tasks.TrackReaderTask(path = utpath("small_legacy"))
    ctrl.opentrack(read)
    assert len(events['opentrack']) == 1
    assert tuple(tuple(ite) for ite in ctrl.tasklist(...)) == ((read,),)

    dum0  = _DummyTask0()
    dum1  = _DummyTask1()
    dum2  = _DummyTask2()

    ctrl.addtask(read, dum0)
    assert len(events['addtask']) == 1
    assert tuple(tuple(ite) for ite in ctrl.tasklist(...)) == ((read,dum0),)

    ctrl.addtask(read, dum1)
    assert len(events['addtask']) == 2
    assert tuple(tuple(ite) for ite in ctrl.tasklist(...)) == ((read,dum0,dum1),)

    ctrl.addtask(read, dum2)
    assert len(events['addtask']) == 3
    assert tuple(tuple(ite) for ite in ctrl.tasklist(...)) == ((read,dum0,dum1,dum2),)

    assert ctrl.cache(read, dum0)() is None
    assert ctrl.cache(read, dum1)() is None
    assert ctrl.cache(read, dum2)() is None

    ctrl.run(read, dum1)

    assert ctrl.cache(read, dum0)() is None
    assert ctrl.cache(read, dum1)() is None
    assert ctrl.cache(read, dum2)() is None

    tuple(ctrl.run(read, dum1))
    assert ctrl.cache(read, dum0)() == [0]
    assert ctrl.cache(read, dum1)() is None
    assert ctrl.cache(read, dum2)() is None

    cnt[0] = 1
    tuple(ctrl.run(read, dum2))
    assert ctrl.cache(read, dum0)() == [0]
    assert ctrl.cache(read, dum1)() is None
    assert ctrl.cache(read, dum2)() == [1]

    cnt[0] = 2
    tuple(ctrl.run(read, dum2))
    assert ctrl.cache(read, dum0)() == [0]
    assert ctrl.cache(read, dum1)() is None
    assert ctrl.cache(read, dum2)() == [2]

    ctrl.updatetask(read, dum1, toto = 2)
    assert len(events['updatetask']) == 1
    assert dum1.toto                 == 2
    assert ctrl.cache(read, dum0)()  == [0]
    assert ctrl.cache(read, dum1)()  is None
    assert ctrl.cache(read, dum2)()  is None

    tuple(ctrl.run(read, dum2))
    assert ctrl.cache(read, dum2)() == [2]

    ctrl.removetask(read, dum1)
    assert len(events['removetask'])                  == 1
    assert tuple(tuple(ite) for ite in ctrl.tasklist(...)) == ((read,dum0,dum2),)
    assert ctrl.cache(read, dum2)()                   is None

    ctrl.closetrack(read)
    assert len(events['closetrack'])                  == 1
    assert tuple(tuple(ite) for ite in ctrl.tasklist(...)) == tuple()

def test_task_closure():
    "testing that closures don't include too many side-effects"
    # pylint: disable=unused-variable, too-many-locals,invalid-name
    # pylint: disable=too-many-statements,missing-docstring,no-self-use
    class TCycles1(tasks.Task):
        level = tasks.Level.cycle

    class TC1Proc(Processor):
        tasktype = TCycles1
        @Processor.action
        def run(self, _):
            return lambda x: x

    def _testClosure(task):
        good = [] # type: ignore
        try:
            Runner.checkClosure(lambda x: (task, x)[1])
        except MemoryError:
            good += [1]
        try:
            Runner.checkClosure(lambda x: (lambda: task, x)[1])
        except MemoryError:
            good += [2]

        try:
            Runner.checkClosure(lambda x, y = task: x)
        except MemoryError:
            good += [3]

        try:
            Runner.checkClosure(lambda x: (lambda z=task:None,x)[1])
        except MemoryError:
            good += [4]

        try:
            def _gen():
                yield task
            Runner.checkClosure(_gen())
        except MemoryError:
            good += [5]

        assert good == [1,2,3,4,5]

    for task in (TCycles1(), Cache(), TC1Proc(TCycles1())):
        _testClosure(task)

def test_task_cache():
    "Tests that actions can be cached"
    # pylint: disable=unused-variable, too-many-locals,invalid-name
    # pylint: disable=too-many-statements,missing-docstring,no-self-use
    class TBeads(tasks.Task):
        level = tasks.Level.bead
        def __init__(self):
            super().__init__()
            self.dummy = None

    calls = []
    class TBProc(Processor):
        tasktype = TBeads
        @Processor.cache
        def run(self, _):
            def _outp(_, x):
                calls.append(1)
                return x
            return _outp

    ctrl = TaskController()
    read = tasks.TrackReaderTask(path = utpath("small_legacy"))
    tb   = TBeads()
    ctrl.opentrack(read, (read, tb))

    assert ctrl.cache(read, tb)() is None
    ctrl.run(read, tb)
    dt = ctrl.cache(read, tb)()
    assert dt                     is not None
    assert len(dt)                == 0

    tuple(ctrl.run(read, tb))
    assert len(dt) == 1
    assert len(next(iter(dt.values()))) == 0

    tuple(bead for frame in ctrl.run(read, tb) for bead in frame)
    sz = len(calls)
    assert len(next(iter(dt.values()))) == sz

    tuple(ctrl.run(read, tb))
    assert len(calls) == sz

    ctrl.updatetask(read, tb, dummy = 1)
    assert ctrl.cache(read, tb)() is None
    v1 = next(iter(next(ctrl.run(read, tb))))[1]
    v2 = next(iter(ctrl.run(read, read)[0]))[1]
    dt = ctrl.cache(read, tb)()
    assert len(dt) == 1
    assert len(next(iter(dt.values()))) == 1
    assert numpy.array_equal(v1, v2)
    assert v1 is not v2

def test_task_expandandcollapse():
    "Tests expanding/collapsing a generator one level"
    # pylint: disable=unused-variable, too-many-locals,invalid-name
    # pylint: disable=too-many-statements,missing-docstring,no-self-use
    # pylint: disable=unidiomatic-typecheck
    class TBeads(tasks.Task):
        level = tasks.Level.bead
    class TCycle(tasks.Task):
        levelin = tasks.Level.cycle
        levelou = tasks.Level.cycle

    class TBProc(Processor):
        tasktype = TBeads
        def run(self, args):
            args.apply(None, levels = self.levels)

    class TCProc(Processor):
        tasktype = TCycle
        def run(self, args):
            args.apply(None, levels = self.levels)

    ctrl = TaskController()
    read = tasks.TrackReaderTask(path = utpath("small_pickle"))
    tb   = TBeads()
    tc   = TCycle()
    ctrl.opentrack(read, (read, tc, tb))

    frames = tuple(ctrl.run(read,read))
    assert frozenset(type(fra) for fra in frames) == frozenset((Beads,))
    keys  = set(key for frame in frames for key, _ in frame)
    beads = {i for i in range(74)}
    assert keys == beads

    frames = tuple(ctrl.run(read,tc))
    assert frozenset(type(fra) for fra in frames) == frozenset((Cycles,))

    keys  = set(key for frame in frames for key, _ in frame)
    truth = set((bead, cyc) for bead in beads for cyc in range(15))
    assert keys == truth

    frames = tuple(frame for frame in ctrl.run(read, tb))
    assert frozenset(type(fra) for fra in frames) == frozenset((TrackView,))
    keys  = set(key for frame in frames for key, _ in frame)
    assert keys == beads

    val = frames[0][0]
    assert type(val)    is numpy.ndarray
    assert type(val[0]) is Cycles

def test_replacement():
    "test replacement"
    class Task1(tasks.Task):
        level = tasks.Level.none

    class Task2(tasks.Task):
        level = tasks.Level.none

    class Task3(tasks.Task):
        level = tasks.Level.none

    lst = []
    class Proc1(Processor[Task1]):
        run = staticmethod(lambda _: lst.append('1'))

    class Proc1B(Processor[Task1]):
        run = staticmethod(lambda _: lst.append('1b'))

    class Proc2(Processor[Task2]):
        run = staticmethod(lambda _: lst.append('2'))

    class Proc3(Processor[Task3]):
        run = staticmethod(lambda _: lst.append('3'))

    def _test(good, *order):
        cache = Cache(list(order))
        lst.clear()
        Runner(cache)(copy = False)
        assert ''.join(lst) == good
        with CacheReplacement(cache, Proc1B):
            lst.clear()
            Runner(cache)(copy = False)
            assert ''.join(lst) == good.replace('1', '1b')
        lst.clear()
        Runner(cache)(copy = False)
        assert ''.join(lst) == good

    _test('123', Proc1(), Proc2(), Proc3())
    _test('213', Proc2(), Proc1(), Proc3())
    _test('231', Proc2(), Proc3(), Proc1())

def test_undersampling():
    "test undersampling"
    proc = UndersamplingProcessor()
    proc.task.framerate = 10.
    assert proc.binwidth(proc.task, 31.) == 3
    assert proc.binwidth(proc.task, 29.) == 3
    proc.task.framerate = 30.
    assert proc.binwidth(proc.task, 100.) == 3

if __name__ == '__main__':
    test_undersampling()
