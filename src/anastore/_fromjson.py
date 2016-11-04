#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track Analysis conversion from json'able items."
import  numpy

from    ._utils     import isjsonable, CNT, TPE

_CONTINUE = type('_CONTINUE', tuple(), dict())

class _ItemIO:
    _CONTENTS = {cls.__name__[0]: cls for cls in (set,frozenset,tuple,dict)}
    @classmethod
    def check(cls, val):
        u"returns wether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None) in cls._CONTENTS

    @classmethod
    def run(cls, val, runner):
        u"returns the loaded item"
        return cls._CONTENTS[val[TPE]](runner(val[CNT]))

class _ListIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, list)

    @staticmethod
    def run(val, runner):
        u"returns the loaded item"
        return [runner(ite) for ite in val]

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, dict) and TPE not in val

    @staticmethod
    def run(val, runner):
        u"returns the loaded item"
        return {name: runner(ite) for name, ite in val.items()}

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None).startswith('np')

    @staticmethod
    def run(val, runner):
        u"returns the loaded item"
        if val[TPE] == 'npo':
            return numpy.array(tuple(runner(ite) for ite in val[CNT]),
                               dtype = numpy.object)
        return numpy.array(val[CNT], dtype = val[TPE][2:])

class Runner:
    u"loads json'ables"
    def __init__(self, lookups = None):
        if lookups is None:
            self.lookups = (_ItemIO,)+tuple(_ItemIO.__subclasses__())
        else:
            self.lookups = lookups

    def __call__(self, item):
        if not (isinstance(item, dict) and TPE in item) and isjsonable(item):
            return item

        for cls in self.lookups:
            if cls.check(item):
                return cls.run(item, self)

        assert TPE in item and '.' in item[TPE]

        elems = item.pop(TPE).split('.')
        cls   = getattr(__import__('.'.join(elems[:-1]), fromlist = elems[-1:]),
                        elems[-1])

        return cls(**{name: self(val) for name, val in item.items()})
