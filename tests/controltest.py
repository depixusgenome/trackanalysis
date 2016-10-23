#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Test control"
# pylint: disable=import-error
import  unittest
import  numpy
from    control.lazy            import LazyInstError, LazyInstanciator, LazyDict
from    control.event           import Event, EmitPolicy
from    control.taskcontrol     import TaskControler
from    control.processor       import Processor, Cache, Runner
from    data                    import Cycles, Beads, TrackItems
import  model.task           as tasks

from    testdata import path


class LazyTest(unittest.TestCase):
    u"test lazy stuff"
    def test_instanciator_verify(self):
        u"test instanciator argument verifications"
        with self.assertRaises(LazyInstError):
            LazyInstError.verify(lambda x: None)
            LazyInstError.verify(1)
            LazyInstError.verify("")
        self.assertEqual(LazyInstError.verify(lambda *x, y = 1, **z: None), None)
        self.assertEqual(LazyInstError.verify(lambda y = 1, **z: None), None)
        self.assertEqual(LazyInstError.verify(lambda **z: None), None)

    def test_instanciator(self):
        u"test instanciator"
        lst = []
        class _AnyType:
            def __init__(self):
                lst.append(1)

        fcn  = lambda: _AnyType() # pylint: disable=unnecessary-lambda
        lazy = LazyInstanciator(fcn)
        self.assertEqual(len(lst), 0)

        ans  = lazy()
        self.assertEqual(len(lst), 1)

        ans2 = lazy()
        self.assertEqual(len(lst), 1)
        self.assertTrue(ans is ans2)

    def test_lazydict(self):
        u"test lazydict"
        lst = []

        def _create(name):
            def __init__(_):
                lst.append(name)
            return name, type(name, tuple(), dict(__init__ = __init__))

        for fcn in (iter, dict):
            dico = LazyDict(fcn((_create('l1'), _create('l2'))),
                            **dict((_create('l3'), _create('l4'))))
            self.assertEqual(len(lst), 0)

            self.assertTrue(dico['l1'].__class__.__name__, 'l1')
            self.assertEqual(lst, ['l1'])

            self.assertTrue(dico['l1'].__class__.__name__, 'l1')
            self.assertEqual(lst, ['l1'])

            self.assertTrue('l2' in dico)
            del dico['l2']
            self.assertFalse('l2' in dico)

            self.assertEqual(lst, ['l1'])

            self.assertTrue(dico.pop('l3').__class__.__name__, 'l3')
            self.assertEqual(lst, ['l1', 'l3'])

            self.assertEqual(dico.pop('l3', lambda:111),  111)
            self.assertEqual(lst, ['l1', 'l3'])

            self.assertTrue(dico.get(*_create('l7')).__class__.__name__, 'l7')
            self.assertEqual(lst, ['l1', 'l3', 'l7'])
            self.assertFalse('l7' in dico)

            self.assertEqual(dico.setdefault('l4', None).__class__.__name__, 'l4')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4'])
            self.assertEqual(dico.setdefault('l4', None).__class__.__name__, 'l4')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4'])

            self.assertEqual(dico.setdefault(*_create('l8')).__class__.__name__, 'l8')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4', 'l8'])
            self.assertTrue('l8' in dico)
            self.assertEqual(dico.setdefault('l8', None).__class__.__name__, 'l8')
            self.assertEqual(lst, ['l1', 'l3', 'l7', 'l4', 'l8'])
            self.assertTrue('l8' in dico)
            lst.clear()

class EventTest(unittest.TestCase):
    u"test event stuff"
    def test_events(self):
        u"test event stuff"
        events = Event()
        this   = self

        calls  = []
        class _Ctrl:
            @staticmethod
            @events.emit
            def event1(*_1, **_2):
                u"dummy"
                calls.append("e1")
                return 1

            @classmethod
            @events.emit(returns = EmitPolicy.outasdict)
            def event2(cls, *_1, **_2):
                u"dummy"
                calls.append("e2")
                return dict(name = 'e2')

            @events.emit(returns = EmitPolicy.outastuple)
            def event3(self, *_1, **_2): # pylint: disable=no-self-use
                u"dummy"
                calls.append("e3")
                return ('e3',)

            @staticmethod
            @events.emit(returns = EmitPolicy.nothing)
            def event4(*_1, **_2):
                u"dummy"
                calls.append("e4")
                return ('e4',)

        @events.emit('event5', 'event6')
        def event5(*_1, **_2):
            u"dummy"
            calls.append("e5")
            return ('e5',)

        hdls = []

        class _Obs:
            @staticmethod
            @events.observe
            def onevent1(*args, **kwargs):
                u"dummy"
                this.assertEqual((args, kwargs), hdls[-1])

            @events.observe
            @staticmethod
            def onevent2(**kwargs):
                u"dummy"
                this.assertEqual(kwargs, dict(name = 'e2'))

            @events.observe('event3')
            @staticmethod
            def onevent3(arg):
                u"dummy"
                this.assertEqual(arg, 'e3')

        got = []
        def _got(*args, **kwargs):
            got.append((args, kwargs))
        events.observe('event4', 'event6', _got)

        def onevent5(*args, **kwargs):
            u"dummy"
            self.assertEqual((args, kwargs), hdls[-1])

        events.observe(onevent5)

        ctrl = _Ctrl()
        obs  = _Obs() # pylint: disable=unused-variable

        hdls.append(((1,2,3), dict(tt = 2)))
        ctrl.event1(1,2,3, tt = 2)
        ctrl.event2(1,2,3, tt = 2)
        ctrl.event3(1,2,3, tt = 2)

        self.assertEqual(len(got), 0)
        ctrl.event4(1,2,3, tt = 2)

        self.assertEqual(got, [(tuple(), dict())])

        event5(1,2,3, tt = 2)
        self.assertEqual(got, [(tuple(), dict()),hdls[-1]])

class TaskControlTest(unittest.TestCase):
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

        ctrl = TaskControler()

        events = dict()
        for evt in 'opentrack', 'closetrack', 'addtask', 'removetask', 'updatetask':
            def _obs(*args, name = evt, **kwargs):
                events.setdefault(name, []).append((args, kwargs))
            ctrl.observe(evt, _obs)


        read = tasks.TrackReaderTask(path = path("small_legacy"))
        ctrl.openTrack(read)
        self.assertTrue(len(events['opentrack']), 1)
        self.assertEqual(tuple(tuple(ite) for ite in ctrl.tasktree), ((read,),))

        dum0  = _DummyTask0()
        dum1  = _DummyTask1()
        dum2  = _DummyTask2()

        ctrl.addTask(read, dum0)
        self.assertTrue (len(events['addtask']), 1)
        self.assertEqual(tuple(tuple(ite) for ite in ctrl.tasktree), ((read,dum0),))

        ctrl.addTask(read, dum1)
        self.assertTrue(len(events['addtask']), 2)
        self.assertEqual(tuple(tuple(ite) for ite in ctrl.tasktree), ((read,dum0,dum1),))

        ctrl.addTask(read, dum2)
        self.assertTrue(len(events['addtask']), 3)
        self.assertEqual(tuple(tuple(ite) for ite in ctrl.tasktree), ((read,dum0,dum1,dum2),))

        self.assertEqual(ctrl.cache(read, dum0)(), None)
        self.assertEqual(ctrl.cache(read, dum1)(), None)
        self.assertEqual(ctrl.cache(read, dum2)(), None)

        ctrl.run(read, dum1)

        self.assertEqual(ctrl.cache(read, dum0)(), None)
        self.assertEqual(ctrl.cache(read, dum1)(), None)
        self.assertEqual(ctrl.cache(read, dum2)(), None)

        tuple(ctrl.run(read, dum1))
        self.assertEqual(ctrl.cache(read, dum0)(), [0])
        self.assertEqual(ctrl.cache(read, dum1)(), None)
        self.assertEqual(ctrl.cache(read, dum2)(), None)

        cnt[0] = 1
        tuple(ctrl.run(read, dum2))
        self.assertEqual(ctrl.cache(read, dum0)(), [0])
        self.assertEqual(ctrl.cache(read, dum1)(), None)
        self.assertEqual(ctrl.cache(read, dum2)(), [1])

        cnt[0] = 2
        tuple(ctrl.run(read, dum2))
        self.assertEqual(ctrl.cache(read, dum0)(), [0])
        self.assertEqual(ctrl.cache(read, dum1)(), None)
        self.assertEqual(ctrl.cache(read, dum2)(), [2])

        ctrl.updateTask(read, dum1, toto = 2)
        self.assertTrue(len(events['updatetask']), 1)
        self.assertTrue(dum1.toto, 2)
        self.assertEqual(ctrl.cache(read, dum0)(), [0])
        self.assertEqual(ctrl.cache(read, dum1)(), None)
        self.assertEqual(ctrl.cache(read, dum2)(), None)

        tuple(ctrl.run(read, dum2))
        self.assertEqual(ctrl.cache(read, dum2)(), [2])

        ctrl.removeTask(read, dum1)
        self.assertTrue(len(events['removetask']), 1)
        self.assertEqual(tuple(tuple(ite) for ite in ctrl.tasktree), ((read,dum0,dum2),))
        self.assertEqual(ctrl.cache(read, dum2)(), None)

        ctrl.closeTrack(read)
        self.assertTrue(len(events['closetrack']), 1)
        self.assertEqual(tuple(tuple(ite) for ite in ctrl.tasktree), tuple())

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

            self.assertEqual(good, [1,2,3,4])

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

        ctrl = TaskControler()
        read = tasks.TrackReaderTask(path = path("small_legacy"))
        tb   = TBeads()
        ctrl.openTrack(read, (read, tb))

        self.assertTrue(ctrl.cache(read, tb)() is None)
        ctrl.run(read, tb)
        dt = ctrl.cache(read, tb)()
        self.assertFalse(dt is None)
        self.assertEqual(len(dt), 0)

        tuple(ctrl.run(read, tb))
        self.assertEqual(len(dt), 1)
        self.assertEqual(len(next(iter(dt.values()))), 0)

        tuple(bead for frame in ctrl.run(read, tb) for bead in frame)
        sz = len(calls)
        self.assertEqual(len(next(iter(dt.values()))), sz)

        tuple(ctrl.run(read, tb))
        self.assertEqual(len(calls), sz)

        ctrl.updateTask(read, tb, dummy = 1)
        self.assertTrue(ctrl.cache(read, tb)() is None)
        v1 = next(iter(next(ctrl.run(read, tb))))[1]
        v2 = next(iter(ctrl.run(read, read)[0]))[1]
        dt = ctrl.cache(read, tb)()
        self.assertEqual(len(dt), 1)
        self.assertEqual(len(next(iter(dt.values()))), 1)
        self.assertTrue(numpy.array_equal(v1, v2))
        self.assertFalse(v1 is v2)

    def test_expandandcollapse(self):
        u"Tests expanding/collapsing a generator one level"
        # pylint: disable=unused-variable, too-many-locals,invalid-name
        # pylint: disable=too-many-statements,missing-docstring,no-self-use
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

        ctrl = TaskControler()
        read = tasks.TrackReaderTask(path = path("small_pickle"))
        tb   = TBeads()
        tc   = TCycle()
        ctrl.openTrack(read, (read, tc, tb))

        frames = tuple(ctrl.run(read,read))
        self.assertEqual(frozenset(type(fra) for fra in frames), frozenset((Beads,)))
        keys  = tuple(key for frame in frames for key, _ in frame)
        self.assertEqual(keys, tuple(range(74)))

        frames = tuple(ctrl.run(read,tc))
        self.assertEqual(frozenset(type(fra) for fra in frames), frozenset((Cycles,)))

        keys  = tuple(key for frame in frames for key, _ in frame)
        truth = tuple((bead, cyc) for bead in range(74) for cyc in range(15))
        self.assertEqual(keys, truth)

        frames = tuple(frame for frame in ctrl.run(read, tb))
        self.assertEqual(frozenset(type(fra) for fra in frames), frozenset((TrackItems,)))
        keys  = tuple(key for frame in frames for key, _ in frame)
        self.assertEqual(keys, tuple(range(74)))
        self.assertEqual(type(frames[0][0]),    numpy.ndarray)
        self.assertEqual(type(frames[0][0][0]), Cycles)

if __name__ == '__main__':
    unittest.main()
