#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Test control"
# pylint: disable=import-error
import  numpy
from    control.event           import Event, EmitPolicy
from    control.taskcontrol     import TaskController
from    control.processor       import Processor, Cache, Runner
from    data                    import Cycles, Beads, TrackItems
import  model.task           as tasks

from    testdata import path

# pylint: disable=no-self-use

class TestEvent:
    u"test event stuff"
    def test_events(self):
        u"test event stuff"
        # pylint: disable=no-self-use,missing-docstring
        events = Event()

        calls  = []
        class _Ctrl:
            @staticmethod
            @events.emit(returns = EmitPolicy.inputs)
            def event1(*_1, **_2):
                calls.append("e1")
                return 1

            @classmethod
            @events.emit
            def event2(cls, *_1, **_2) -> dict:
                calls.append("e2")
                return dict(name = 'e2')

            @events.emit
            def event3(self, *_1, **_2) -> tuple:
                calls.append("e3")
                return ('e3',)

            @staticmethod
            @events.emit
            def event4(*_1, **_2) -> None:
                calls.append("e4")

        @events.emit('event5', 'event6', returns = EmitPolicy.inputs)
        def event5(*_1, **_2):
            calls.append("e5")
            return ('e5',)

        hdls = []

        class _Obs:
            @staticmethod
            @events.observe
            def onevent1(*args, **kwargs):
                assert (args, kwargs) == hdls[-1]

            @events.observe
            @staticmethod
            def onevent2(**kwargs):
                assert kwargs == dict(name = 'e2')

            @events.observe('event3')
            @staticmethod
            def onevent3(arg):
                assert arg == 'e3'

        got = []
        def _got(*args, **kwargs):
            got.append((args, kwargs))
        events.observe('event4', 'event6', _got)

        def onevent5(*args, **kwargs):
            assert (args, kwargs) == hdls[-1]

        events.observe(onevent5)

        ctrl = _Ctrl()
        obs  = _Obs() # pylint: disable=unused-variable

        hdls.append(((1,2,3), dict(tt = 2)))
        ctrl.event1(1,2,3, tt = 2)
        ctrl.event2(1,2,3, tt = 2)
        ctrl.event3(1,2,3, tt = 2)

        assert len(got) == 0
        ctrl.event4(1,2,3, tt = 2)

        assert got == [(tuple(), dict())]

        event5(1,2,3, tt = 2)
        assert got == [(tuple(), dict()),hdls[-1]]

    def test_observewithdict(self):
        u"test event stuff"
        # pylint: disable=no-self-use,missing-docstring,unnecessary-lambda,multiple-statements
        events = Event()

        def _add(ind):
            # pylint: disable=unused-argument
            def _fcn(self, *_1, **_2):
                return dict(name = 'e%d' % ind)
            _fcn.__name__ = _fcn.__name__.replace('_fcn', 'event%d') % ind
            _fcn.__qualname__ = _fcn.__qualname__.replace('_fcn', 'event%d') % ind

            return _fcn.__name__, events.emit(_fcn, returns = EmitPolicy.outasdict)

        ctrl = type('_Ctrl', tuple(), dict(_add(i) for i in range(8)))()

        got  = []
        def onEvent3(name = None, **_):
            got.append(name)
        def _onEvent4(name = None, **_):
            got.append(name)
        def _onEvent6(name = None, **_):
            got.append(name)
        def _onEvent7(name = None, **_):
            got.append(name)

        events.observe({'event1': lambda **_: onEvent3(**_),
                        'event2': _onEvent4})
        events.observe(onEvent3, _onEvent4)
        events.observe(event5 = _onEvent4)
        events.observe([_onEvent6, _onEvent7])

        for i in range(1, 8):
            getattr(ctrl, 'event%d' % i)()
        assert got == ['e%d'% i for i in range(1, 8)]

class TestTaskControl:
    u"testing task control"
    def test_taskmutations(self):
        u"testing task control"
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
        _DummyTask0, _DummyProcess0 = _make(0, lambda i, j: j.setCacheDefault(i, list(cnt)))
        _DummyTask1, _DummyProcess1 = _make(1, lambda i, j: None)
        _DummyTask2, _DummyProcess2 = _make(2, lambda i, j: j.setCache(i, list(cnt)))

        ctrl = TaskController()

        events = dict()
        for evt in 'opentrack', 'closetrack', 'addtask', 'removetask', 'updatetask':
            def _obs(*args, name = evt, **kwargs):
                events.setdefault(name, []).append((args, kwargs))
            ctrl.observe(evt, _obs)


        read = tasks.TrackReaderTask(path = path("small_legacy"))
        ctrl.openTrack(read)
        assert len(events['opentrack']) == 1
        assert tuple(tuple(ite) for ite in ctrl.tasktree) == ((read,),)

        dum0  = _DummyTask0()
        dum1  = _DummyTask1()
        dum2  = _DummyTask2()

        ctrl.addTask(read, dum0)
        assert len(events['addtask']) == 1
        assert tuple(tuple(ite) for ite in ctrl.tasktree) == ((read,dum0),)

        ctrl.addTask(read, dum1)
        assert len(events['addtask']) == 2
        assert tuple(tuple(ite) for ite in ctrl.tasktree) == ((read,dum0,dum1),)

        ctrl.addTask(read, dum2)
        assert len(events['addtask']) == 3
        assert tuple(tuple(ite) for ite in ctrl.tasktree) == ((read,dum0,dum1,dum2),)

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

        ctrl.updateTask(read, dum1, toto = 2)
        assert len(events['updatetask']) == 1
        assert dum1.toto                 == 2
        assert ctrl.cache(read, dum0)()  == [0]
        assert ctrl.cache(read, dum1)()  is None
        assert ctrl.cache(read, dum2)()  is None

        tuple(ctrl.run(read, dum2))
        assert ctrl.cache(read, dum2)() == [2]

        ctrl.removeTask(read, dum1)
        assert len(events['removetask'])                  == 1
        assert tuple(tuple(ite) for ite in ctrl.tasktree) == ((read,dum0,dum2),)
        assert ctrl.cache(read, dum2)()                   is None

        ctrl.closeTrack(read)
        assert len(events['closetrack'])                  == 1
        assert tuple(tuple(ite) for ite in ctrl.tasktree) == tuple()

    def test_closure(self):
        u"testing that closures don't include too many side-effects"
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
            good = []
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

            assert good == [1,2,3,4]

        for task in (TCycles1(), Cache(), TC1Proc(TCycles1())):
            _testClosure(task)

    def test_cache(self):
        u"Tests that actions can be cached"
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
                def _outp(x):
                    calls.append(1)
                    return x
                return _outp

        ctrl = TaskController()
        read = tasks.TrackReaderTask(path = path("small_legacy"))
        tb   = TBeads()
        ctrl.openTrack(read, (read, tb))

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

        ctrl.updateTask(read, tb, dummy = 1)
        assert ctrl.cache(read, tb)() is None
        v1 = next(iter(next(ctrl.run(read, tb))))[1]
        v2 = next(iter(ctrl.run(read, read)[0]))[1]
        dt = ctrl.cache(read, tb)()
        assert len(dt) == 1
        assert len(next(iter(dt.values()))) == 1
        assert numpy.array_equal(v1, v2)
        assert v1 is not v2

    def test_expandandcollapse(self):
        u"Tests expanding/collapsing a generator one level"
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
        read = tasks.TrackReaderTask(path = path("small_pickle"))
        tb   = TBeads()
        tc   = TCycle()
        ctrl.openTrack(read, (read, tc, tb))

        frames = tuple(ctrl.run(read,read))
        assert frozenset(type(fra) for fra in frames) == frozenset((Beads,))
        keys  = set(key for frame in frames for key, _ in frame)
        beads = set(tuple(range(74))+('t', 'zmag'))
        assert keys == beads

        frames = tuple(ctrl.run(read,tc))
        assert frozenset(type(fra) for fra in frames) == frozenset((Cycles,))

        keys  = set(key for frame in frames for key, _ in frame)
        truth = set((bead, cyc) for bead in beads for cyc in range(15))
        assert keys == truth

        frames = tuple(frame for frame in ctrl.run(read, tb))
        assert frozenset(type(fra) for fra in frames) == frozenset((TrackItems,))
        keys  = set(key for frame in frames for key, _ in frame)
        assert keys == beads

        val = tuple(frames[0][0])[0][1]
        assert type(val)    is numpy.ndarray
        assert type(val[0]) is Cycles
