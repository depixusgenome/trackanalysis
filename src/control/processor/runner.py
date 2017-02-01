#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with running a list of processes"
from typing         import (Callable, Optional,     # pylint: disable=unused-import
                            Iterable, Tuple)
from inspect        import signature
from itertools      import groupby
import numpy

from data           import TrackItems, createTrackItem
from model          import Task, Level
from .base          import Processor
from .cache         import Cache

class Runner:
    u"Arguments used for iterating"
    __slots__ = ('data', 'level', 'gen')
    def __init__(self, data):
        self.data  = data      # type: Cache
        self.gen   = None      # type: Optional[TrackItems]
        self.level = Level(0)

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
        def _test(item):
            refused = (Task, Processor, Cache, cls)

            if isinstance(item, refused):
                raise MemoryError("Beware of closure side-effecs:"
                                  +" exclude {} from it".format(refused))

            cls.checkClosure(item)

        if callable(fcn):
            for param in signature(fcn).parameters.values():
                if param.default != param.empty:
                    _test(param.default)

        closure = getattr(fcn, '__closure__', None)
        if closure is not None:
            for cell in closure:
                _test(cell.cell_contents)

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
            self.gen = iter(fcn(frame) for frame in gen)
        else:
            raise NotImplementedError("What to do with " + str(fcn) + "?")

    first = property(lambda self: self.data.first)

def run(data, tsk = None):
    u"""
    Iterates through the list up to and including *tsk*.
    Iterates through all if *tsk* is None
    """
    args = Runner(data)
    ind  = None if tsk is None else data.index(tsk)+1
    for proc in data[:ind]:
        proc.run(args)
    return args.gen
