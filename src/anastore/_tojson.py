#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track Analysis conversion to json'able items."
from    abc     import ABCMeta, abstractmethod
from    enum    import Enum
import  numpy

from    ._utils import isjsonable

class _ItemIO(metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def check(val):
        u"returns wether this class deals with val"

    @staticmethod
    @abstractmethod
    def run(val, runner):
        u"returns the dict to be dumped"

class _ContainerIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, (set, frozenset, tuple))

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        return {"c": type(val).__name__[0], "v": runner(list(val))}

class _ListIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, list)

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        return [runner(ite) for ite in val]

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, dict)

    @staticmethod
    def run(val, runner):
        u"returns the dict to be dumped"
        if all(isinstance(key, str) for key in val):
            if isjsonable(val):
                return val
            else:
                return {name: runner(ite) for name, ite in val.items()}
        else:
            vals = [[runner(name), runner(ite)] for name, ite in val.items()]
            return {'c': 'd', 'v': vals}

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        u"returns wether this class deals with val"
        return isinstance(val, numpy.ndarray)

    @staticmethod
    def run(val, runner):
        u"returns thishe dict to be dumped"
        if val.dtype == numpy.object:
            vals = [runner(ite) for ite in val]
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
        return val.name

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
