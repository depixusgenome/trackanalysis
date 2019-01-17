#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Lazy collections"

from  inspect import signature, Parameter
from  typing  import Callable, Any

class LazyInstError(Exception):
    u"Exception that verifies that a callable is provided to LazyInstanciator"
    @classmethod
    def verify(cls, fcn:Callable):
        u"Verifies that a callable is provided to LazyInstanciator"
        if not callable(fcn):
            raise cls("Value must be callable: "+str(fcn))

        for _, par in signature(fcn).parameters.items():
            if par.default is not par.empty:
                continue
            if par.kind is Parameter.POSITIONAL_OR_KEYWORD:
                raise cls("Value must be callable *without* arguments")

class LazyInstanciator:
    u"Stores a method to be called only when needed"
    def __init__(self, fcn:Callable[[],Any]) -> None:
        LazyInstError.verify(fcn)
        self._call = fcn
        self._data = None   # type: Any

    def __call__(self):
        if self._call is not None:
            self._data = self._call()
            self._call = None
        return self._data

class LazyDict:
    u"Behaves as a dict but stores LazyInstanciators as values and releases their data"
    def __init__(self, _lazy_args_ = None, **kwargs):
        self._data = dict()
        self.update(_lazy_args_, **kwargs)

    def update(self, _lazy_args_ = None, **kwargs):
        u"as for dict"
        if _lazy_args_ is not None:
            # pylint: disable=not-an-iterable
            for key, val in getattr(_lazy_args_, 'items', lambda: _lazy_args_)():
                self[key] = LazyInstanciator(val)

        for key, val in kwargs.items():
            self[key] = LazyInstanciator(val)

    def get(self, key, default = None):
        u"as for dict"
        val =  self._data.get(key, None)
        return default() if val is None else val()

    def setdefault(self, key, default = None):
        u"as for dict"
        val = self._data.get(key, None)
        if val is None and default is not None:
            val             = LazyInstanciator(default)
            self._data[key] = val
        return val()

    def popitem(self, keeplazy = False):
        u"as for dict"
        if keeplazy:
            return self._data.popitem()
        key, val = self._data.popitem()
        return key, val()

    def pop(self, key, default = None, keeplazy = False):
        u"as for dict"
        if keeplazy:
            return self._data.pop(key, default)

        val = self._data.pop(key, default)
        if val is None:
            val = LazyInstanciator(default)

        return val()

    def __iter__(self):
        u"as for dict"
        return iter(self._data)

    def __getitem__(self, key):
        u"as for dict"
        return self._data[key]()

    def __delitem__(self, key) -> None:
        u"as for dict"
        del self._data[key]

    def __setitem__(self, key, val) -> None:
        u"as for dict"
        self._data[key] = LazyInstanciator(val)

    def __len__(self) -> int:
        u"as for dict"
        return len(self._data)
