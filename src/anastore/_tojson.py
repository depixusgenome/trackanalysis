#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track Analysis conversion to json'able items."
from    abc     import ABCMeta, abstractmethod
from    enum    import Enum
from    pathlib import Path
from    pickle  import dumps as _dumps
import  numpy   as     np

from    ._utils import isjsonable, CNT, TPE, STATE, STAR

class _ItemIO(metaclass=ABCMeta):
    @staticmethod
    @abstractmethod
    def check(val):
        "returns wether this class deals with val"

    @staticmethod
    @abstractmethod
    def run(val, runner):
        "returns the dict to be dumped"

class _TypeIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, type)

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        return {TPE: 'τ', CNT: f"{val.__module__}.{val.__qualname__}"}

class _ContainerIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, (set, frozenset, tuple))

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        tpe  = type(val)
        if tpe in (set, frozenset, tuple):
            return {TPE: tpe.__name__[0], CNT: runner(list(val))}
        name =  f"{tpe.__module__}.{tpe.__qualname__}"
        return {TPE: tpe.__base__.__name__[0], STAR: name, CNT: runner(list(val))}

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
            return (val if isjsonable(val) else
                    {name: runner(ite) for name, ite in val.items()})

        vals = [[runner(name), runner(ite)] for name, ite in val.items()]
        return {TPE: 'd', CNT: vals}

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, np.ndarray)

    @staticmethod
    def run(val, runner):
        "returns thishe dict to be dumped"
        if val.dtype == getattr(np, 'object'):
            vals = [runner(ite) for ite in val]
            return {TPE: 'npo', CNT: vals}
        return {TPE: 'np'+str(val.dtype), CNT: val.tolist()}

class _NDScalarIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return np.isscalar(val)

    @staticmethod
    def run(val, runner):
        "returns thishe dict to be dumped"
        return val.tolist() if type(val).__module__ == 'numpy' else val

class _NPFunction(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return getattr(np, getattr(val, '__name__', '_'), None) is val

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

class _PathIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns wether this class deals with val"
        return isinstance(val, Path)

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        return str(val)

class Runner:
    "runs item to json'able object"
    _Dummy = type('_Dummy', (), {})
    def __init__(self, lookups = None, saveall = True):
        if lookups is None:
            self.lookups = tuple(_ItemIO.__subclasses__())
        else:
            self.lookups = lookups
        self.saveall = saveall

    def __call__(self, item):
        if isjsonable(item):
            return item

        for cls in self.lookups:
            if cls.check(item):
                return cls.run(item, self)

        dico  = dict()
        attrs = self.__state(item)

        cls = type(item)
        if self.saveall is False:
            fcn = getattr(item, '__ana_default__', None)
            if callable(fcn):
                attrs = fcn(attrs)

            for name, val in attrs:
                if self._isdefault(cls, name, val):
                    continue

                state = self(val)
                if not (isinstance(state, dict) and len(state) == 1 and TPE in state):
                    dico[name] = state
        else:
            for name, val in attrs:
                dico[name] = self(val)

        tpe       = item.__class__
        dico[TPE] = f"{tpe.__module__}.{tpe.__qualname__}"
        return dico

    @staticmethod
    def __state(item):
        if hasattr(item, '__getstate__'):
            state = item.__getstate__()
            return state.items() if isinstance(state, dict) else ((STATE, state),)
        return getattr(item, '__dict__', {}).items()

    def _isdefault(self, tpe, name, val) -> bool:
        default = getattr(tpe, name, self._Dummy)
        if type(default) is type(val):
            if isinstance(val, np.ndarray):
                if (val.shape == default.shape
                        and val.dtype == default.dtype
                        and all(i == j for i, j in zip(val, default))):
                    return True
            elif val == default or _dumps(val) == _dumps(default):
                return True
        return False
