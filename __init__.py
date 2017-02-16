#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"utils"
from copy           import deepcopy
from contextlib     import contextmanager
from inspect        import (signature, ismethod as _ismeth, isfunction as _isfunc,
                            getmembers, isgeneratorfunction, stack as _stack)
from functools      import wraps
import re
import pathlib
from typing         import Union, Optional, Callable, IO, cast # pylint: disable=unused-import
from types          import LambdaType, FunctionType, MethodType
from enum           import Enum
import numpy as np

def toenum(tpe, val):
    u"returns an enum object"
    if isinstance(val, str):
        return tpe.__members__[val]
    elif isinstance(val, int):
        return tpe(val)
    elif isinstance(val, tpe):
        return val
    elif val is not None:
        raise TypeError('"level" attribute has incorrect type')

def isfunction(fcn) -> bool:
    u"Returns whether the object is a function"
    return isinstance(fcn, (LambdaType, FunctionType, MethodType))

def ismethod(fcn) -> bool:
    u"to be called in method decorators"
    if isinstance(fcn, cast(type, classmethod)):
        return True

    elif next(iter(signature(fcn).parameters), '') in ('self', 'cls', 'mcs'):
        return True

    return False

def coffee(apath:'Union[str,pathlib.Path]', name:'Optional[str]' = None, **kwa) -> str:
    u"returns the javascript implementation code"
    path = pathlib.Path(apath)
    if name is not None:
        path = path.parent / name # type: ignore

    src = pathlib.Path(path.with_suffix(".coffee")).read_text()
    for name, val in kwa.items():
        src = src.replace("$$"+name, val)
    return src.replace('$$', '')

class MetaMixin(type):
    u"""
    Mixes base classes together.

    Mixin classes are actually composed. That way there are fewer name conflicts
    """
    def __new__(mcs, clsname, bases, nspace, **kw):
        mixins = kw['mixins']
        def setMixins(self, instances = None, initargs = None):
            u"sets-up composed mixins"
            for base in mixins:
                name =  base.__name__.lower()
                if instances is not None and name in instances:
                    setattr(self, name, instances[name])
                elif getattr(self, name, None) is None:
                    if initargs is not None:
                        setattr(self, name, base(**initargs))
                    else:
                        setattr(self, name, base())

        nspace['setMixins'] = setMixins

        def getMixin(self, base):
            u"returns the mixin associated with a class"
            return getattr(self, base.__name__.lower(), None)

        nspace['getMixin'] = getMixin

        init = nspace.get('__init__', lambda *_1, **_2: None)
        def __init__(self, **kwa):
            init(self, **kwa)
            for base in bases:
                base.__init__(self, **kwa)
            self.setMixins(mixins, initargs = kwa)

        nspace['__init__'] = __init__
        nspace.update(mcs.__addaccesses(mixins, nspace, kw))

        mnames = tuple(base.__name__.lower() for base in mixins)
        nspace['_mixins'] = property(lambda self: (getattr(self, i) for i in mnames))

        dummy = lambda *_1, **_2: tuple()

        def _callmixins(self, name, *args, **kwa):
            for mixin in getattr(self, '_mixins'):
                getattr(mixin, name, dummy)(*args, **kwa)
        nspace['_callmixins'] = _callmixins

        def _yieldovermixins(self, name, *args, **kwa):
            for mixin in getattr(self, '_mixins'):
                yield from getattr(mixin, name, dummy)(*args, **kwa)
        nspace['_yieldovermixins'] = _yieldovermixins

        return type(clsname, bases, nspace)

    @classmethod
    def __addaccesses(mcs, mixins, nspace, kwa):
        match   = re.compile(kwa.get('match', r'^[a-z][a-zA-Z0-9]+$')).match
        members = dict()
        for base in mixins:
            for name, fcn in getmembers(base):
                if match(name) is None or name in nspace:
                    continue
                members.setdefault(name, []).append((base, fcn))

        for name, fcns in members.items():
            if len(set(j for _, j in fcns)) > 1:
                if not kwa.get('selectfirst', False):
                    raise NotImplementedError("Multiple funcs: "+str(fcns))

            base, fcn = fcns[0]
            if _ismeth(fcn) or (_isfunc(fcn) and not ismethod(fcn)):
                yield (name, mcs.__createstatic(fcn))
            elif _isfunc(fcn):
                yield (name, mcs.__createmethod(base, fcn))
            elif isinstance(fcn, Enum):
                yield (name, fcn)
            elif isinstance(fcn, property):
                yield (name, mcs.__createprop(base, fcn))

    @staticmethod
    def __createstatic(fcn):
        @wraps(fcn)
        def _wrap(*args, **kwa):
            return fcn(*args, **kwa)
        return staticmethod(_wrap)

    @staticmethod
    def __createmethod(base, fcn, ):
        cname = base.__name__.lower()
        @wraps(fcn)
        def _wrap(self, *args, **kwa):
            return fcn(getattr(self, cname), *args, **kwa)
        return _wrap

    @staticmethod
    def __createprop(base, prop):
        fget = (None if prop.fget is None
                else lambda self: prop.fget(self.getMixin(base)))
        fset = (None if prop.fset is None
                else lambda self, val: prop.fset(self.getMixin(base), val))
        fdel = (None if prop.fdel is None
                else lambda self: prop.fdel(self.getMixin(base)))

        return property(fget, fset, fdel, prop.__doc__)

def fromstream(streamopts):
    u"wraps a method using a stream as first input: it can now use str, Path or streams"
    def _wrapper(fcn):
        tpe   = 'Union[str,pathlib.Path,IO]'
        first = next(iter(signature(fcn).parameters))
        if isgeneratorfunction(fcn):
            @wraps(fcn)
            def _wrapgen(path, *args, **kwa):
                if isinstance(path, pathlib.Path):
                    path = str(path)

                if isinstance(path, str):
                    with open(path, streamopts) as stream:
                        yield from fcn(stream, *args, **kwa)
                else:
                    yield from fcn(path, *args, **kwa)

            _wrapgen.__annotations__[first] = tpe
            return _wrapgen
        else:
            @wraps(fcn)
            def _wrapfcn(path, *args, **kwa):
                if isinstance(path, pathlib.Path):
                    path = str(path)

                if isinstance(path, str):
                    with open(path, streamopts) as stream:
                        return fcn(stream, *args, **kwa)
                else:
                    return fcn(path, *args, **kwa)

            _wrapfcn.__annotations__[first] = tpe
            return _wrapfcn
    return _wrapper

@contextmanager
def _escapenans(*arrays: np.ndarray, reset = True):
    if len(arrays) == 0:
        yield tuple()
        return

    if len({arr.shape for arr in arrays}) > 1:
        raise ValueError("all arrays must have the same shape")

    nans = np.zeros_like(arrays[0], dtype = 'bool')
    for arr in arrays:
        nans |= np.isnan(arr)

    if any(nans):
        yielded = tuple(arr[~nans] for arr in arrays)

        if len(yielded) == 1:
            yield yielded[0]
        else:
            yield yielded

        if reset:
            for cur, arr in zip(yielded, arrays):
                arr[~nans] = cur
    else:
        if len(arrays) == 1:
            yield arrays[0]
        else:
            yield arrays

def escapenans(*arrays: np.ndarray, reset = True):
    u"""
    Allows removing nans from arrays prior to a computation and putting
    them back inside afterwards:

        >>> import numpy as np
        >>> array1, array2 = np.arange(10), np.ones((10,))
        >>> array1[[0,5]] = np.nan
        >>> array2[[1,6]] = np.nan
        >>> with escapenan(array1, array2) as (cur1, cur2):
        >>>     assert not any(np.isnan(cur1)) and not any(np.isnan(cur2))
        >>>     cur1 += cur2
        >>> inds = [2,3,4,7,8,9]
        >>> assert all(array1[inds] ==  (np.arange(10)+1)[inds])
        >>> assert all(np.isnan(array1[[0,5]]))
        >>> assert all(array1[[1,6]] == [1,6])
        >>> assert all(np.isnan(array2[[1,6]]))
        >>> assert all(array2[[0,5]] == 1)

    Can also be used as a wrapper:

        >>> import numpy as np
        >>> inds   = [2,3,4,7,8,9]
        >>> array1 = np.arange(10)
        >>> array1[[0,1,5,6]] = np.nan
        >>> def _fcn(x):
        ...    assert not any(np.isnan(x))
        ...    x[:] += 1
        >>> wrapped = escapenan(_fcn)
        >>> wrapped(array1)
        >>> assert all(array1[inds] ==  (np.arange(10)+1)[inds])
        >>> assert all(np.isnan(array1[[0,1,5,6]]))
    """
    if len(arrays) == 1 and callable(arrays[0]):
        fcn = arrays[0]
        def _wrap(*arrs):
            with _escapenans(*arrs, reset = reset) as currs:
                return fcn(*currs)
        return _wrap
    else:
        return _escapenans(*arrays, reset = reset)

@contextmanager
def changefields(self, __items__ = None, **items):
    u"Context within which given fields are momentarily changed"
    if __items__ is not None:
        items.update(__items__)

    olds = {}
    for name, kwdef in items.items():
        olds[name] = old = getattr(self, name)

        if isinstance(old, Enum):
            kwdef  = old.__class__(kwdef)

        setattr(self, name, kwdef)

    yield olds

    for i, j in olds.items():
        setattr(self, i , j)

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
                return fcn(self, *args, **kwargs)
        return _wrap

    if len(items) == 1 and callable(items[0]):
        return _wrapper(items[0])
    return _wrapper

def initdefaults(*attrs, roots = ('',)):
    u"""
    Uses the class attribute to initialize the object's fields if no keyword
    arguments were provided.
    """
    fcn = None
    if len(attrs) == 1 and isinstance(attrs[0], tuple):
        attrs = attrs[0]

    if len(attrs) == 1 and callable(attrs[0]):
        fcn   = attrs[0]
        attrs = ()

    if len(attrs) == 0:
        attrs = tuple(i for i in _stack()[1][0].f_locals.keys())

    assert len(attrs) and all(isinstance(i, str) for i in attrs)
    attrs = tuple(i for i in attrs if i[0].upper() != i[0])

    none = type('None', (), {})
    def _wrapper(fcn):
        @wraps(fcn)
        def __init__(self, *args, **kwargs):
            fcn(self, *args, **kwargs)
            for name in attrs:
                clsdef = getattr(self.__class__, name)
                for root in roots:
                    kwdef = kwargs.get(root+name, none)

                    if kwdef is none:
                        continue

                    if isinstance(clsdef, Enum):
                        setattr(self, name, clsdef.__class__(kwdef))
                    else:
                        setattr(self, name, kwdef)
                        break
                else:
                    setattr(self, name, deepcopy(clsdef))
        return __init__

    return _wrapper if fcn is None else _wrapper(fcn)
