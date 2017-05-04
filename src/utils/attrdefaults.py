#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"utils"

from    typing         import (TypeVar, Iterable, # pylint: disable=unused-import
                               FrozenSet, Optional, Callable, Sequence, Dict, Any)
import  inspect
from    copy           import deepcopy, copy
from    functools      import wraps
from    enum           import Enum

from   .inspection     import getlocals

NoArgs = type('NoArgs', (), {})

def toenum(tpe, val):
    "returns an enum object"
    if not isinstance(tpe, type):
        tpe = type(tpe)

    if not issubclass(tpe, Enum):
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
    "Context within which given fields are momentarily changed"
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
    "Context within which given fields are momentarily changed"
    return ChangeFields(obj, __items__, **items)

def kwargsdefaults(*items, asinit = True):
    """
    Keyword arguments are used for changing an object's fields before running
    the method.

    Using *asinit* means the same attributes as for __init__ will be allowed.
    This is only valid if initdefaults decorates the __init__
    """
    def _fields(vals):
        assert len(vals) and all(isinstance(i, str) for i in vals)
        accepted = frozenset(vals)
        return lambda _: accepted

    if len(items) == 1 and isinstance(items[0], Iterable) and not isinstance(items[0], str):
        items = items[0]

    if len(items):
        items = tuple(i for i in items if i[0].upper() != i[0])

    call = len(items) == 1 and callable(items[0])
    if call:
        if not asinit:
            fields = fieldnames
        else:
            pot    = getattr(getlocals(1).get('__init__', None), 'KEYS', None)
            fields = fieldnames if pot is None else _fields(pot)
    else:
        fields = fieldnames if not len(items)            else _fields(items)

    def _wrapper(fcn):
        @wraps(fcn)
        def _wrap(self, *args, **kwargs):
            if len(kwargs):
                tochange = {i: kwargs.pop(i) for i in fields(self) & frozenset(kwargs)}
                if len(tochange):
                    with changefields(self, tochange):
                        return fcn(self, *args, **kwargs)

            return fcn(self, *args, **kwargs)
        return _wrap

    return _wrapper(items[0]) if call else _wrapper

def setdefault(self, name, kwargs, roots = ('',), # pylint: disable=too-many-arguments
               cpy = None, deepcpy = None):
    """
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
        if deepcpy is not None:
            setattr(self, name, deepcopy(getattr(cpy, name)))
        elif cpy is not None:
            setattr(self, name, getattr(cpy, name))
        else:
            setattr(self, name, deepcopy(clsdef))

class _Updater:
    __slots__ = ('roots', 'mandatory', 'update', 'call', 'attrs', 'pipes', 'ignore')
    def __init__(self,
                 attrs:Sequence[str],
                 roots:Sequence[str],
                 mandatory: bool,
                 kwa:Dict[str,str]) -> None:
        self.roots     = roots
        self.mandatory = mandatory

        kwa            = {i: (j.lower() if isinstance(j, str) else j)
                          for i, j in kwa.items()}
        self.update    = tuple(i for i in attrs if kwa.get(i, '') == 'update')
        self.call      = tuple((i, j) for i, j in kwa.items() if callable(j))
        self.ignore    = tuple(i for i in attrs if kwa.get(i, '') == 'ignore')
        self.attrs     = tuple(i for i in attrs
                               if (kwa.get(i, '') != 'ignore'
                                   and not callable(kwa.get(i, ''))))
        self.pipes     = None        # type: Optional[Sequence[Any]]

    def __init(self, obj):
        cls        = type(obj)
        self.pipes = tuple(i for i in self.attrs
                           if isinstance(cls.__dict__.get(i, None), AttrPipe))
        self.attrs = tuple(i for i in self.attrs if i not in self.pipes)

    def __call__(self, obj, kwargs, cpy = None, deepcpy = None):
        if self.pipes is None:
            self.__init(obj)

        pipes = tuple(i for i in self.pipes if i in kwargs)

        for name in self.attrs:
            if self.mandatory and cpy is None and deepcpy is None and name not in kwargs:
                raise KeyError("Missing keyword '%s' in __init__" % name)
            else:
                setdefault(obj, name, kwargs, self.roots, cpy, deepcpy)

        for name in self.update:
            update(getattr(obj, name), **kwargs)

        for name in pipes:
            setattr(obj, name, toenum(getattr(type(obj), name), kwargs[name]))

        for name, fcn in self.call:
            if name in kwargs:
                fcn(obj, kwargs[name])

def initdefaults(*attrs, roots = ('',), mandatory = False, **kwa):
    """
    Uses the class attribute to initialize the object's fields if no keyword
    arguments were provided.
    """
    fcn = None
    if len(attrs) == 1 and isinstance(attrs[0], Iterable) and not isinstance(attrs[0], str):
        attrs = attrs[0]

    if len(attrs) == 1 and callable(attrs[0]):
        fcn   = attrs[0]
        attrs = ()

    if len(attrs) == 0:
        attrs = tuple(i for i in getlocals(1).keys())

    assert len(attrs) and all(isinstance(i, str) for i in attrs)
    attrs = tuple(i for i in attrs if i[0].upper() != i[0])

    def _wrapper(fcn):
        val     = tuple(inspect.signature(fcn).parameters.values())[1]
        updater = _Updater(attrs, roots, mandatory, kwa)
        if val.kind  == val.VAR_KEYWORD:
            @wraps(fcn)
            def __init__(self, *args, **kwargs):
                fcn(self, **kwargs)
                if len(args) > 1:
                    raise TypeError("__init__ takes at most a single positional"
                                    +" argument as a copy constructor")
                elif len(args) == 1:
                    updater(self, kwargs, cpy = args[0])
                else:
                    updater(self, kwargs)
            __init__.KEYS = attrs
            return __init__
        else:
            @wraps(fcn)
            def __init__(self, *args, **kwargs):
                fcn(self, *args, **kwargs)
                updater(self, kwargs)
            __init__.KEYS = attrs
            return __init__

    return _wrapper if fcn is None else _wrapper(fcn)

T = TypeVar('T')
def fieldnames(obj) -> FrozenSet[str]:
    "Returns attribute and property names of the object"
    dico = frozenset(name
                     for name in getattr(obj, '__dict__', ())
                     if 'a' <= name[0] <= 'z')
    desc = frozenset(name
                     for name, tpe in obj.__class__.__dict__.items()
                     if ('a' <= name[0] <= 'z'
                         and callable(getattr(tpe, '__set__', None))
                         and not getattr(tpe, 'fset', '') is None))
    return dico | desc # type: ignore

def _update(cpy: Optional[Callable[[T], T]], obj:T, **attrs) -> T:
    "Sets field to provided values"
    fields = fieldnames(obj) & frozenset(attrs)
    if len(fields):
        if cpy:
            obj = cpy(obj)
        for name in fieldnames(obj) & frozenset(attrs):
            setattr(obj, name, attrs[name])
    return obj

def update(obj:T, **attrs) -> T:
    "Sets field to provided values"
    return _update(None, obj, **attrs)

def updatecopy(obj:T, **attrs) -> T:
    "Sets field to provided values on a copied object"
    return _update(copy, obj, **attrs)

def updatedeepcopy(obj:T, **attrs) -> T:
    "Sets field to provided values on a deepcopied object"
    return _update(deepcopy, obj, **attrs)

class AttrPipe:
    "Pipes a field to a parent"
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
    "Pipes a field to a parent"
    return AttrPipe(name)
