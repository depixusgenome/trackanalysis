#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track Analysis conversion to json'able items."
from    abc     import ABCMeta, abstractmethod
from    enum    import Enum
import  pickle
import  numpy

from    ._utils import isjsonable

class _ItemIO(metaclass=ABCMeta):
    @abstractmethod
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"

    @abstractmethod
    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"

class _ContainerIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, (set, frozenset, list, tuple))

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        return {"c": type(val).__name__[0],
                "v": tuple(runner(ite) for ite in val)}

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, dict)

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        return {name: runner(ite) for name, ite in val.items()}

_MAXNPARRAY = 100
class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, numpy.ndarray)

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        if val.dtype is not numpy.object and len(val) > _MAXNPARRAY:
            return dict(c = 'pk',                v = pickle.dumps(val))
        elif val.dtype is numpy.object:
            vals = tuple(runner(ite) for ite in val)
            return dict(c = 'npo',               v = vals)
        else:
            return dict(c = 'np'+str(val.dtype), v = val.tolist())

class _EnumIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, Enum)

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        return val.name()

class Runner:
    u"runs item to json'able object"
    def __init__(self, lookups = None):
        if lookups is None:
            self.lookups = tuple(_ItemIO.__subclasses__())
        else:
            self.lookups = lookups

    def __call__(self, item):
        if isjsonable(item):
            return item

        for cls in self.lookups:
            if cls.check(item):
                return cls.run(item, self)

        dico = dict()
        for name, val in item.__dict__.items():
            dico[name] = self(val)

        dico['c'] = item.__class__.__module__+'.'+item.__class__.__name__
        return dico
