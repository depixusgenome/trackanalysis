#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track Analysis conversion to json'able items."
from    abc     import ABCMeta, abstractmethod
from    enum    import Enum
import  numpy

from    ._utils import isjsonable, CNT, TPE, STATE

class _ItemIO(metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def check(val):
        "returns wether this class deals with val"

    @staticmethod
    @abstractmethod
    def run(val, runner):
        "returns the dict to be dumped"

class _ContainerIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, (set, frozenset, tuple))

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        return {TPE: type(val).__name__[0], CNT: runner(list(val))}

class _ListIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, list)

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        return [runner(ite) for ite in val]

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, dict)

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        if all(isinstance(key, str) for key in val):
            if isjsonable(val):
                return val
            else:
                return {name: runner(ite) for name, ite in val.items()}
        else:
            vals = [[runner(name), runner(ite)] for name, ite in val.items()]
            return {TPE: 'd', CNT: vals}

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, numpy.ndarray)

    @staticmethod
    def run(val, runner):
        "returns thishe dict to be dumped"
        if val.dtype == numpy.object:
            vals = [runner(ite) for ite in val]
            return {TPE: 'npo', CNT: vals}
        else:
            return {TPE: 'np'+str(val.dtype), CNT: val.tolist()}

class _NPFunction(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return getattr(numpy, getattr(val, '__name__', '_'), None) is val

    @staticmethod
    def run(val, runner):
        "returns thishe dict to be dumped"
        return TPE+val.__name__

class _EnumIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, Enum)

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        return val.name

class Runner:
    "runs item to json'able object"
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

        dico  = dict()
        attrs = getattr(item, '__dict__', {}).items()
        if hasattr(item, '__getstate__'):
            state = item.__getstate__()
            if isinstance(state, dict):
                attrs = state.items()
            else:
                attrs = (STATE, state),

        for name, val in attrs:
            dico[name] = self(val)

        dico[TPE] = item.__class__.__module__+'.'+item.__class__.__qualname__
        return dico
