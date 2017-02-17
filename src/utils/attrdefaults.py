#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"

from copy           import deepcopy
from functools      import wraps
from typing         import Iterable
from enum           import Enum
from .inspection    import getlocals

NoArgs = type('NoArgs', (), {})

def toenum(tpe, val):
    u"returns an enum object"
    if not isinstance(tpe, type):
        tpe = type(tpe)

    if not isinstance(tpe, Enum):
        return val
    elif isinstance(val, str):
        return tpe.__members__[val]
    elif isinstance(val, int):
        return tpe(val)
    elif isinstance(val, tpe):
        return val
    elif val is not None:
        raise TypeError('"level" attribute has incorrect type')

class ChangeFields:
    u"Context within which given fields are momentarily changed"
    def __init__(self, obj, __items__ = None, **items):
        self.obj = obj
        if __items__ is not None:
            items.update(__items__)
        self.items = items
        self.olds  = dict()

    def __enter__(self):
        for name, kwdef in self.items.items():
            self.olds[name] = old = getattr(self.obj, name)

            kwdef = toenum(old, kwdef)

            setattr(self.obj, name, kwdef)
        return self.olds

    def __exit__(self, *_):
        for i, j in self.olds.items():
            setattr(self.obj, i , j)

def changefields(obj, __items__ = None, **items):
    u"Context within which given fields are momentarily changed"
    return ChangeFields(obj, __items__, **items)

def kwargsdefaults(*items):
    u"""
    Keyword arguments are used for changing an object's fields before running
    the method
    """
    if len(items) == 1 and isinstance(items[0], tuple):
        items = items[0]

    if len(items) == 1 and callable(items[0]):
        fields   = lambda x: frozenset(i for i in x.__dict__ if i[0] != i[0].upper())
    else:
        assert len(items) and all(isinstance(i, str) for i in items)
        accepted = frozenset(items)
        fields   = lambda _: accepted

    def _wrapper(fcn):
        @wraps(fcn)
        def _wrap(self, *args, **kwargs):
            tochange = {i: kwargs.pop(i) for i in fields(self) & frozenset(kwargs)}
            with changefields(self, tochange):
                ret = fcn(self, *args, **kwargs)
            return ret
        return _wrap

    if len(items) == 1 and callable(items[0]):
        return _wrapper(items[0])
    return _wrapper

def setdefault(self, name, kwargs, roots = ('',)):
    u"""
    Uses the class attribute to initialize the object's fields if no keyword
    arguments were provided.
    """
    clsdef = getattr(type(self), name)
    for root in roots:
        kwdef = kwargs.get(root+name, NoArgs)

        if kwdef is NoArgs:
            continue

        setattr(self, name, toenum(clsdef, kwdef))
        break
    else:
        setattr(self, name, deepcopy(clsdef))

def initdefaults(*attrs, roots = ('',), **kwa):
    u"""
    Uses the class attribute to initialize the object's fields if no keyword
    arguments were provided.
    """
    fcn = None
    if len(attrs) == 1 and isinstance(attrs[0], Iterable):
        attrs = attrs[0]

    if len(attrs) == 1 and callable(attrs[0]):
        fcn   = attrs[0]
        attrs = ()

    if len(attrs) == 0:
        attrs = tuple(i for i in getlocals(1).keys())

    assert len(attrs) and all(isinstance(i, str) for i in attrs)
    attrs = tuple(i for i in attrs if i[0].upper() != i[0])

    def _wrapper(fcn):
        @wraps(fcn)
        def __init__(self, *args, **kwargs):
            fcn(self, *args, **kwargs)
            pipes = []
            cls   = type(self)
            for name in attrs:
                if isinstance(cls.__dict__.get(name, None), AttrPipe):
                    val = kwargs.get(name, NoArgs)
                    if val is not NoArgs:
                        pipes.append((name, kwargs[name]))
                else:
                    setdefault(self, name, kwargs, roots)

            for name, val in kwa.items():
                if val.lower() == 'update':
                    update(getattr(self, name), **kwargs)
                elif val.lower() == 'set':
                    setdefault(self, name, kwargs, roots)

            for name, val in pipes:
                setattr(self, name, toenum(getattr(cls, name), val))

        return __init__

    return _wrapper if fcn is None else _wrapper(fcn)

def update(obj, **attrs):
    u"Sets field to provided values"
    for name in frozenset(getattr(obj, '__dict__', ())) & frozenset(attrs):
        setattr(obj, name, attrs[name])

class AttrPipe:
    u"Pipes a field to a parent"
    def __init__(self, name: str) -> None:
        self.name = name.split('.')

    def __get__(self, obj, tpe):
        if obj is None:
            obj = tpe

        for i in self.name:
            obj = getattr(obj, i)
        return obj

    def __set__(self, obj, val):
        for i in self.name[:-1]:
            obj = getattr(obj, i)
        setattr(obj, self.name[-1], val)

def pipe(name: str) -> AttrPipe:
    u"Pipes a field to a parent"
    return AttrPipe(name)
