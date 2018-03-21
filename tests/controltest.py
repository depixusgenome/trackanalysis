#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Test control"
# pylint: disable=import-error,missing-docstring
from    pathlib                 import Path
from    typing                  import Dict, Callable, cast
import  tempfile
import  numpy
import pytest
from    control.globalscontrol  import GlobalsController
from    control.event           import Event, EmitPolicy
from    control.taskcontrol     import TaskController
from    control.processor       import Processor, Cache, Runner
from    control.processor.cache import CacheReplacement
from    control.decentralized   import DecentralizedController
from    data.views              import Cycles, Beads, TrackView
import  model.task           as tasks

from    testingcore             import path as utpath

def test_evt():
    "test event stuff"
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

    hdls = [] # type: ignore

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

def test_evt_observewithdict():
    "test event stuff"
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
    _DummyTask0, _DummyProcess0 = _make(0, lambda i, j: j.setCacheDefault(i, list(cnt)))
    _DummyTask1, _DummyProcess1 = _make(1, lambda i, j: None)
    _DummyTask2, _DummyProcess2 = _make(2, lambda i, j: j.setCache(i, list(cnt)))

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
    beads = {i for i in range(74)} | {'t', 'zmag'}
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

def test_globals(): # pylint: disable=too-many-statements
    "testing globals"
    ctrl = GlobalsController()
    ctrl.addGlobalMap("toto", titi = 1)
    assert ctrl.getGlobal("toto").titi.get() == 1 # pylint: disable=no-member
    assert ctrl.getGlobal("toto").titi == 1

    ctrl.getGlobal("toto").titi = 2
    assert ctrl.getGlobal("toto").titi.get() == 2 # pylint: disable=no-member
    assert ctrl.getGlobal("toto").titi == 2

    ctrl.updateGlobal("toto", titi = 3)
    assert ctrl.getGlobal("toto").titi.get() == 3 # pylint: disable=no-member
    assert ctrl.getGlobal("toto").titi  == 3

    ctrl.updateGlobal("toto", titi = 3)
    assert ctrl.getGlobal("toto").titi  == 3
    del ctrl.getGlobal("toto")['titi']
    assert ctrl.getGlobal("toto").titi == 1

    del ctrl.getGlobal("toto").titi
    assert ctrl.getGlobal("toto").titi == 1

    ctrl.updateGlobal("toto", titi = 3)
    assert ctrl.getGlobal("toto").titi  == 3
    ctrl.getGlobal("toto").pop("titi")
    assert ctrl.getGlobal("toto").titi == 1

    with pytest.raises(KeyError):
        ctrl.getGlobal("toto").mm.pp = 1

    ctrl.getGlobal("toto").tintin.default = 11
    ctrl.updateGlobal("toto", titi = 3)
    ctrl.getGlobal("toto").tata.default = 11
    ctrl.addGlobalMap("tut", tata = 11)
    ctrl.getGlobal("toto").tata = 10
    ctrl.getGlobal("tut").tata = 10
    ctrl.addGlobalMap("toto.mm", tata = 11)
    ctrl.getGlobal("toto.mm").tata = 10

    path  = tempfile.mktemp()+"/config.txt"
    cpath = lambda *_: Path(path)
    assert not Path(path).exists()
    ctrl.writeconfig(cpath)
    assert Path(path).exists()

    ctrl.getGlobal("toto").tintin.default = 10
    del ctrl.getGlobal("toto").titi
    del ctrl.getGlobal("toto.mm").tata
    assert ctrl.getGlobal("toto.mm").tata == 11
    assert ctrl.getGlobal("toto").titi == 1
    ctrl.getGlobal("toto").titi.default = 2
    ctrl.removeGlobalMap("tut")
    with pytest.raises(KeyError):
        ctrl.getGlobal("tut")

    ctrl.readconfig(cpath)
    assert ctrl.getGlobal("toto.mm").tata == 10
    assert ctrl.getGlobal("toto").tintin == 10
    assert ctrl.getGlobal("toto").titi == 3
    del ctrl.getGlobal("toto").titi
    assert ctrl.getGlobal("toto").titi == 2

    with pytest.raises(KeyError):
        ctrl.getGlobal("tut")
    with pytest.raises(KeyError):
        ctrl.getGlobal("toto").tutu.get()

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
        Runner(cache)()
        assert ''.join(lst) == good
        with CacheReplacement(cache, Proc1B):
            lst.clear()
            Runner(cache)()
            assert ''.join(lst) == good.replace('1', '1b')
        lst.clear()
        Runner(cache)()
        assert ''.join(lst) == good

    _test('123', Proc1(), Proc2(), Proc3())
    _test('213', Proc2(), Proc1(), Proc3())
    _test('231', Proc2(), Proc3(), Proc1())

def test_decentralized():
    "test decentralized"
    # pylint: disable=too-many-statements,missing-docstring
    class Toto:
        name = 'toto'
        aval = 1
        bval = ""
        def __init__(self):
            self.aval = 2
            self.bval = ""

    class Tata(Dict):
        """
        Model for key bindings
        """
        name = 'toto'

    def _test(obj): # pylint: disable=too-many-statements
        ctrl = DecentralizedController()
        ctrl.add(obj)
        cnt = [0, 0]
        get = cast(Callable, dict.__getitem__  if isinstance(obj, dict) else getattr)
        def _fcn1(**_):
            cnt[0] += 1
        def _fcn2(**_):
            cnt[1] += 1
        ctrl.observe("totodefaults", _fcn1)
        ctrl.observe("toto",         _fcn2)
        cmap  = ctrl.chainmaps['toto']
        assert len(cmap.maps[0]) == 0
        assert cmap.maps[1] == {'aval': 2, 'bval': ""}

        ctrl.updatedefaults("toto", aval = 3)
        assert cnt == [1, 1]
        assert get(ctrl.model('toto'), 'aval') == 3
        assert get(ctrl.model('toto'), 'bval') == ""
        cmap  = ctrl.chainmaps['toto']
        assert len(cmap.maps[0]) == 0
        assert cmap.maps[1] == {'aval': 3, 'bval': ""}

        ctrl.updatedefaults("toto", aval = 3)
        assert cnt == [1, 1]

        ctrl.update("toto", aval = 3)
        assert cnt == [1, 1]

        ctrl.update("toto", aval = 4)
        assert cnt == [1, 2]
        assert get(ctrl.model('toto'), 'aval') == 4
        assert get(ctrl.model('toto'), 'bval') == ""
        cmap  = ctrl.chainmaps['toto']
        assert cmap.maps[0] == {'aval': 4}
        assert cmap.maps[1] == {'aval': 3, 'bval': ""}

        ctrl.updatedefaults("toto", aval = 6)
        assert cnt == [2, 2]
        assert get(ctrl.model('toto'), 'aval') == 4
        assert get(ctrl.model('toto'), 'bval') == ""
        cmap  = ctrl.chainmaps['toto']
        assert cmap.maps[0] == {'aval': 4}
        assert cmap.maps[1] == {'aval': 6, 'bval': ""}

        try:
            ctrl.update("toto", newval = 5)
        except KeyError:
            pass
        else:
            assert False

        if isinstance(obj, dict):
            ctrl.updatedefaults('toto', newval = 5)
            assert cnt == [3, 3]
            assert get(ctrl.model('toto'), 'aval') == 4
            assert get(ctrl.model('toto'), 'bval') == ""
            assert get(ctrl.model('toto'), 'newval') == 5
            cmap  = ctrl.chainmaps['toto']
            assert cmap.maps[0] == {'aval': 4}
            assert cmap.maps[1] == {'aval': 6, 'bval': "", 'newval': 5}

            ctrl.update('toto', newval = 10)
            assert cnt == [3, 4]
            assert get(ctrl.model('toto'), 'newval') == 10

            ctrl.updatedefaults('toto', newval = ctrl.DELETE)
            assert cnt == [4, 5]
            assert get(ctrl.model('toto'), 'aval') == 4
            assert get(ctrl.model('toto'), 'bval') == ""
            cmap  = ctrl.chainmaps['toto']
            assert cmap.maps[0] == {'aval': 4}
            assert cmap.maps[1] == {'aval': 6, 'bval': ""}
        else:
            try:
                ctrl.updatedefaults('toto', aval = ctrl.DELETE)
            except ValueError:
                pass
            else:
                assert False

        cnt[0] = cnt[1] = 0
        ctrl.update('toto', aval = ctrl.DELETE)
        assert cnt == [0, 1]
        assert get(ctrl.model('toto'), 'aval') == 6
        assert get(ctrl.model('toto'), 'bval') == ""
        cmap  = ctrl.chainmaps['toto']
        assert len(cmap.maps[0]) == 0
        assert cmap.maps[1] == {'aval': 6, 'bval': ""}

    _test(Toto())
    _test(Tata(aval = 2, bval = ""))

if __name__ == '__main__':
    test_decentralized()
