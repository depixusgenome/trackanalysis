#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track Analysis conversion from json'able items."
import  pickle
import  numpy

from    model.level import Level
from    ._utils     import isjsonable

_CONTINUE = type('_CONTINUE', tuple(), dict())

class _ItemIO:
    _CONTENTS = {cls.__name__[0]: cls for cls in (set, frozenset,list,tuple)}
    @classmethod
    def check(cls, val):
        u"returns wether this class deals with val"
        return val.get('c', None) in cls._CONTENTS

    @classmethod
    def run(cls, val, runner):
        u"returns the loaded item"
        return cls._CONTENTS[val['c']](runner(ite) for ite in val)

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, dict) and 'c' not in val

    @staticmethod
    def run(val, runner):
        u"returns the loaded item"
        return {name: runner(ite) for name, ite in val}

class _PickleIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return val.get('c', None)  == 'pk'

    @staticmethod
    def run(val, _):
        u"returns the loaded item"
        return pickle.loads(val.get('v'))

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return val.get('c', None).startswith('np')

    @staticmethod
    def run(val, runner):
        u"returns the loaded item"
        if val['c'] == 'npo':
            return numpy.array(tuple(runner(ite) for ite in val['v']),
                               dtype = numpy.object)
        return numpy.array(val['v'], dtype = val['c'][2:])

def _enumio(enu):
    mbrs = enu.__members__

    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        if isinstance(val, dict) and val.get('level', None) in mbrs:
            val['level'] = mbrs[val['level']]
        return False

    return type('_'+enu.__name__+'IO', (_ItemIO,), dict(check = check))

_LevelIO = _enumio(Level)

class Runner:
    u"loads json'ables"
    def __init__(self, lookups = None):
        if lookups is None:
            self.lookups = tuple(_ItemIO.__subclasses__())
        else:
            self.lookups = lookups

    def __call__(self, item):
        if not (isinstance(item, dict) and 'c' in item) and isjsonable(item):
            return item

        for cls in self.lookups:
            if cls.check(item):
                return cls.run(item, self)

        assert 'c' in item and '.' in item['c']

        elems = item.pop('c').split('.')
        cls   = __import__('.'.join(elems[:-1]), fromlist = elems[-1:])
        for elem in elems[1:]:
            cls = getattr(cls, elem)

        dico = dict()
        for name, val in item.items():
            dico[name] = self(val)
        return cls(**dico)
