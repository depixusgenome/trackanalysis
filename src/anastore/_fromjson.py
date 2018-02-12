#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track Analysis conversion from json'able items."
from    typing      import cast
from    importlib   import import_module

import  numpy       as     np

from    ._utils     import isjsonable, CNT, STAR, STATE, TPE

_CONTINUE = type('_CONTINUE', tuple(), dict())
def _loadclass(name:str) -> type:
    "loads and returns a class"
    elems = name.split('.')
    cur   = elems[0]
    cls   = import_module(cur)
    for i in elems[1:]:
        cur += '.' + i
        cls  = getattr(cls, i, _CONTINUE)
        if cls is _CONTINUE:
            cls  = import_module(cur)
    return cast(type, cls)

class _ItemIO:
    _CONTENTS = {cls.__name__[0]: cls for cls in (set,frozenset,tuple,dict)}
    @classmethod
    def check(cls, val):
        "returns whether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None) in cls._CONTENTS

    @classmethod
    def run(cls, val, runner):
        "returns the loaded item"
        if STAR in val:
            return _loadclass(val[STAR])(*runner(val[CNT]))
        return cls._CONTENTS[val[TPE]](runner(val[CNT]))

class _TypeIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns whether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None) == 'τ'

    @classmethod
    def run(cls, val, runner):
        return _loadclass(val[CNT])

class _ListIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns whether this class deals with val"
        return isinstance(val, list)

    @staticmethod
    def run(val, runner):
        "returns the loaded item"
        return [runner(ite) for ite in val]

class _DictIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns whether this class deals with val"
        return isinstance(val, dict) and TPE not in val

    @staticmethod
    def run(val, runner):
        "returns the loaded item"
        return {name: runner(ite) for name, ite in val.items()}

class _NDArrayIO(_ItemIO):
    @staticmethod
    def check(val):
        "returns whether this class deals with val"
        return isinstance(val, dict) and val.get(TPE, None).startswith('np')

    @staticmethod
    def run(val, runner):
        "returns the loaded item"
        if val[TPE] == 'npo':
            return np.array(tuple(runner(ite) for ite in val[CNT]),
                            dtype = np.object)
        return np.array(val[CNT], dtype = val[TPE][2:])

class _NPFunction(_ItemIO):
    @staticmethod
    def check(val):
        "returns whether this class deals with val"
        return isinstance(val, str) and val.startswith(TPE)

    @staticmethod
    def run(val, runner):
        "returns the dict to be dumped"
        return getattr(np, val[1:])

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

        obj = self.__create_obj(item.pop(TPE))
        return self.__init_obj(obj, item)

    @staticmethod
    def __create_obj(item):
        cls = _loadclass(item)

        if hasattr(cls, '__getnewargs_ex__'):
            i, j = cls.__getnewargs_ex__()              # type: ignore
            return cls.__new__(*i, **j)
        if hasattr(cls, '__getnewargs__'):
            return cls.__new__(*cls.__getnewargs__())   # type: ignore
        return cls.__new__(cls)                         # type: ignore

    def __init_obj(self, obj, item):
        state = {name: self(val) for name, val in item.items()}
        state = state.get(STATE, state)
        if hasattr(obj, '__setstate__'):
            getattr(obj, '__setstate__')(state)
        elif hasattr(obj, '__init__') and getattr(obj.__init__, 'IS_GET_STATE', False):
            obj.__init__(**state)
        else:
            obj.__dict__.update(state)
        return obj
