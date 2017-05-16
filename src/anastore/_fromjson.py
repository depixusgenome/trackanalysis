#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track Analysis conversion from json'able items."
import  numpy

from    ._utils     import isjsonable, CNT, TPE, STATE

_CONTINUE = type('_CONTINUE', tuple(), dict())

class _ItemIO:
    _CONTENTS = {cls.__name__[0]: cls for cls in (set,frozenset,tuple,dict)}
    @classmethod
    def check(cls, val):
        "returns wether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None) in cls._CONTENTS

    @classmethod
    def run(cls, val, runner):
        "returns the loaded item"
        return cls._CONTENTS[val[TPE]](runner(val[CNT]))

class _ListIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, list)

    @staticmethod
    def run(val, runner):
        "returns the loaded item"
        return [runner(ite) for ite in val]

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, dict) and TPE not in val

    @staticmethod
    def run(val, runner):
        "returns the loaded item"
        return {name: runner(ite) for name, ite in val.items()}

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None).startswith('np')

    @staticmethod
    def run(val, runner):
        "returns the loaded item"
        if val[TPE] == 'npo':
            return numpy.array(tuple(runner(ite) for ite in val[CNT]),
                               dtype = numpy.object)
        return numpy.array(val[CNT], dtype = val[TPE][2:])

class _NPFunction(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, str) and val.startswith(TPE)

    @staticmethod
    def run(val, runner):
        "returns thishe dict to be dumped"
        return getattr(numpy, val[1:])

class Runner:
    "loads json'ables"
    def __init__(self, lookups = None):
        if lookups is None:
            self.lookups = (_ItemIO,)+tuple(_ItemIO.__subclasses__())
        else:
            self.lookups = lookups

    def __call__(self, item):
        if not ((isinstance(item, (str, dict)) and TPE in item)) and isjsonable(item):
            return item

        for cls in self.lookups:
            if cls.check(item):
                return cls.run(item, self)

        assert TPE in item and '.' in item[TPE]

        elems = item.pop(TPE).split('.')
        for i in range(-1, -len(elems), -1):
            try:
                cls = getattr(__import__('.'.join(elems[:i]), fromlist = elems[i]),
                              elems[i])
            except ImportError:
                continue
            for j in range(i+1, 0):
                cls = getattr(cls, elems[j])
            break
        else:
            raise ImportError('Could not load class '+ '.'.join(elems))

        if hasattr(cls, '__getnewargs_ex__'):
            i, j = cls.__getnewargs_ex__()
            obj = cls.__new__(*i, **j)
        elif hasattr(cls, '__getnewargs__'):
            obj = cls.__new__(*cls.__getnewargs__())
        else:
            obj = cls.__new__(cls)

        state = {name: self(val) for name, val in item.items()}
        state = state.get(STATE, state)
        if hasattr(obj, '__setstate__'):
            getattr(obj, '__setstate__')(state)
        else:
            obj.__dict__.update(state)
        return obj
