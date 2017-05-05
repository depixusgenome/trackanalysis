#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with running a list of processes"
from inspect            import signature
from itertools          import groupby
from functools          import partial
from multiprocessing    import cpu_count
from copy               import copy as shallowcopy
from typing             import (Callable,   # pylint: disable=unused-import
                                Iterable, Tuple, Dict, Any, Sequence,
                                Optional, Iterator, cast)
import pickle

import numpy

from data               import TrackItems, createTrackItem
from model              import Task, Level
from .base              import Processor
from .cache             import Cache

class Runner:
    u"Arguments used for iterating"
    __slots__ = ('data', 'pool', 'level', 'gen')
    def __init__(self, data, pool = None, gen = None):
        self.data  = data      # type: Cache
        self.pool  = pool      # type: Any
        self.gen   = gen       # type: Optional[Iterator[TrackItems]]
        self.level = Level(0)

    def __getstate__(self):
        return {'data': self.data}

    def __setstate__(self, values):
        self.__init__(values['data'])

    def __getitem__(self, sli) -> Cache:
        "creates a Cache object with all tasks between start and end"
        return Cache(self.data[sli])

    def poolkwargs(self, task) -> Dict[str, Any]:
        "returns kwargs needed for a pool"
        return dict(pool = self.pool, data = self[:task])

    @property
    def model(self) -> Iterator[Task]:
        "returns the model"
        return iter(i.proc.task for i in self.data)

    @staticmethod
    def regroup(grp) -> 'Callable':
        u"regroups elements with a same key into an numpy.ndarray"
        def _regroup(cols = tuple(grp)):
            data = dict()
            for col in cols:
                data.setdefault(col.parents[-1], []).append(col)
            for key in data:
                data[key] = numpy.array(data[key])
            return data
        return _regroup

    def tolevel(self, curr: 'Optional[Tuple[Level,Level]]'):
        u"Changes a generator to fit the processor's level"
        if curr in (None, Level.none):
            return

        old  = self.level
        gen  = self.gen

        if gen is None:
            self.level = curr[1]
            return

        def collapse(gen):
            u"""
            Collapses items from *gen* into a series of *TrackItem*s
            each of which contain sequential items with similar parents
            """
            for key, grp in groupby(gen, key = lambda frame: frame.parents[:-1]):
                yield TrackItems(data = self.regroup(grp), parents = key)

        def expand(level:Level, gen):
            u"Transforms *gen* into *TrackItem*s, one per item in gen"
            yield from (createTrackItem(level,
                                        track   = frame.track,
                                        data    = frame[[key]],
                                        parents = frame.parents+(key,))
                        for frame in gen for key in frame.keys())

        inp = curr[0]
        while old is not inp:
            asc = old.value < inp.value
            old = Level (old.value+(1 if asc else -1))
            gen = expand(old, gen)    if asc else collapse(gen)
        self.gen   = gen
        self.level = curr[1]

    @classmethod
    def checkClosure(cls, fcn):
        u"""
        We want the closure to be frozen.

        In this way, changing the task after implementing the iteration
        should have no effect.
        """
        try:
            cls.__check(fcn)
        except MemoryError as exc:
            raise cls.__exception(fcn) from exc


    def apply(self, fcn, *_, levels = None):
        u"Applies a function to generator's output"
        self.tolevel(levels)
        if fcn is None:
            pass
        elif isinstance(fcn, Iterable):
            self.gen = fcn
        elif callable(fcn):
            self.checkClosure(fcn)
            gen      = self.gen
            if gen is None:
                self.gen = fcn()
            else:
                self.gen = iter(fcn(frame) for frame in gen)
        else:
            raise NotImplementedError("What to do with " + str(fcn) + "?")

    first = property(lambda self: self.data.first)

    __REFUSED = (Task, Processor, Cache)

    @classmethod
    def __exception(cls, item):
        return MemoryError("Beware of closure side-effecs:"
                           +" exclude {} from ".format(cls.__REFUSED)
                           +str(item))
    @classmethod
    def __test(cls, item):
        if isinstance(item, cls.__REFUSED) or isinstance(item, cls):
            raise cls.__exception(item)
        cls.__check(item)

    @classmethod
    def __check(cls, arg):
        if arg is None:
            return

        if callable(arg):
            for param in signature(arg).parameters.values():
                if param.default != param.empty:
                    cls.__test(param.default)

        closure = getattr(arg, '__closure__', None)
        if closure is not None:
            for cell in closure:
                cls.__test(cell.cell_contents)

        givars = getattr(getattr(arg,    'gi_code', None), 'co_freevars', tuple())
        giloc  = getattr(getattr(arg, 'gi_frame', None), 'f_locals', {})
        for var in givars:
            cls.__test(giloc.get(var, None))

def poolchunk(items, nproc, iproc):
    "returns a chunk of keys"
    if isinstance(items, Iterator):
        items = tuple(items)

    nkeys    = len(items) if hasattr(items, '__len__') else items
    nperproc = nkeys // nproc
    rem      = nkeys %  nproc
    istart   = nperproc * iproc     + min(rem, iproc)
    istop    = nperproc * (iproc+1) + min(rem, iproc+1)
    sli      = slice(istart, istop)
    return items[sli] if hasattr(items, '__getitem__') else sli

def _m_multi(data, start, parents, nproc, iproc):
    frame = next(i for i in run(data, start = start) if i.parents == parents)
    return {i: frame[i] for i in poolchunk(frame.keys(), nproc, iproc)}

pooldump = pickle.dumps  # pylint: disable=invalid-name
def pooledinput(pool, pickled, frame) -> dict:
    u"returns a dictionary with all input"
    data = pickle.loads(pickled)
    if pool is None or not any(i.isslow() for i in data):
        return dict(frame)

    else:
        res   = {} # type: dict
        nproc = pool.nworkers
        ind   = next((i for i, j in enumerate(list(data)[::-1]) if j.canpool()), None)
        if ind is None:
            gen  = None
        else:
            ind  = len(data)-cast(int, ind)
            gen  = tuple(i.withdata(dict(i.data))
                         for i in run(Cache(data[:ind]))
                         if i.parents == frame.parents[:len(i.parents)])
            data = Cache(data[ind:])

        for val in pool.map(partial(_m_multi, data, gen, frame.parents, nproc), range(nproc)):
            res.update(val)
        return res

def run(data, tsk = None, copy = False, pool = None, start = None):
    u"""
    Iterates through the list up to and including *tsk*.
    Iterates through all if *tsk* is None
    """

    # make sure the original input is not changed
    gen   = iter(shallowcopy(i) for i in start) if start is not None else None

    if pool is not None and not hasattr(pool, 'nworkers'):
        nproc = getattr(pool, '_max_workers', None)
        if nproc is None:
            nproc = cpu_count()
        pool.nworkers = nproc

    args  = Runner(data, pool = pool, gen = gen)
    ind   = None if tsk is None else data.index(tsk)+1
    first = True
    for proc in data[:ind]:
        if not proc.task.disabled:
            proc.run(args)
            if first and copy:
                args.gen = tuple(frame.withcopy(True) for frame in args.gen)
            first  = False
    return args.gen
