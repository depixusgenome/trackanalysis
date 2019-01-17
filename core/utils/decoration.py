#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"decoration utils"

import  pathlib
from    collections import OrderedDict
from    contextlib  import contextmanager
from    functools   import wraps
from    inspect     import signature, isgeneratorfunction
from    typing      import (Dict, Tuple, Any, Optional, TypeVar,
                            Generic, Callable, Union, IO, Iterator, TYPE_CHECKING)
import  numpy as np

StreamUnion = Union[str,pathlib.Path,IO]

class _PathPos:
    def __init__(self, fcn):
        bad  = {'self', 'cls', 'mcs'}
        good = {'path', 'stream'}
        sig  = signature(fcn).parameters
        i, j = next((i for i in enumerate(sig) if i[1] in good), # type: ignore
                    next((i for i in enumerate(sig) if i[1] not in bad),
                         (0, next(iter(sig)))))
        self.ind:  int = i
        self.name: str = j

    def path(self, args, kwa):
        "returns the path arg"
        return kwa['path'] if 'path' in kwa else args[self.ind]

    def args(self, path, args, kwa):
        "returns the args as they should be"
        if 'path' in kwa:
            kwa['path'] = path
        else:
            args = args[:self.ind] + (path,) + args[self.ind+1:]
        return args, kwa

def fromstream(streamopts):
    """
    wraps a method using a stream as input so it can use str, Path or stream

    The stream attribute will be identified as:
    1. the first one named *stream* or *path*
    2. the first which is **not** named *self* or *cls*
    """
    def _wrapper(fcn):
        ppos    = _PathPos(fcn)
        if isgeneratorfunction(fcn):
            @wraps(fcn)
            def _wrapgen(*args, **kwa):
                path = ppos.path(args, kwa)
                if isinstance(path, pathlib.Path):
                    path = str(path)

                if isinstance(path, str):
                    with open(path, streamopts) as stream:
                        args, kwa = ppos.args(stream, args, kwa)
                        yield from fcn(*args, **kwa)
                else:
                    args, kwa = ppos.args(path, args, kwa)
                    yield from fcn(*args, **kwa)

            if TYPE_CHECKING:
                _wrapgen.__annotations__[ppos.name] = StreamUnion # type: ignore
            return _wrapgen

        @wraps(fcn)
        def _wrapfcn2(*args, **kwa):
            path = ppos.path(args, kwa)
            if isinstance(path, pathlib.Path):
                path = str(path)

            if isinstance(path, str):
                with open(path, streamopts) as stream:
                    args, kwa = ppos.args(stream, args, kwa)
                    return fcn(*args, **kwa)
            else:
                args, kwa = ppos.args(path, args, kwa)
                return fcn(*args, **kwa)

        if TYPE_CHECKING:
            _wrapfcn2.__annotations__[ppos.name] = StreamUnion # type: ignore
        return _wrapfcn2
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
    """
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
    return _escapenans(*arrays, reset = reset)

Type = TypeVar("Type")
class CachedIO(Generic[Type]):
    "Caches io output"
    def __init__(self,
                 reader: Callable[..., Type],
                 cache:  Optional[Dict[pathlib.Path, Tuple[int, Any]]] = None,
                 size:   int                                           = 10
                ) -> None:
        self.__reader = reader
        self.__ppos   = _PathPos(reader)
        self.__cache  = OrderedDict() if cache is None else cache
        self.__size   = size

    def values(self):
        "iters over all entries"
        yield from (i for _, i in self.__cache.values())

    def items(self):
        "iters over all entries"
        yield from ((i, j) for i, (_, j) in self.__cache.items())

    def clear(self, path: Optional[Union[str, pathlib.Path]] = None):
        "clears the cache"
        if path is not None:
            self.__cache.pop(pathlib.Path(path).resolve())
        else:
            self.__cache.clear()

    def __call__(self, *args, **kwa) -> Optional[Type]:
        "reads and caches a file"
        path = pathlib.Path(self.__ppos.path(args, kwa)).resolve()
        if not path.exists():               # pylint: disable=no-member
            return None

        info  = self.__cache.pop(path, None)
        mtime = path.stat().st_mtime_ns     # pylint: disable=no-member
        if info is None or info[0] != mtime:
            info = (mtime, self.__reader(*args, **kwa))
            if isinstance(info[1], Iterator):
                info = info[0], tuple(info[1])

            if self.__size == len(self.__cache) and path not in self.__cache:
                self.__cache.popitem()

        self.__cache[path] = info
        return info[1] # type: ignore

def cachedio(fcn):
    "Caches io output"
    return wraps(fcn)(CachedIO(fcn).__call__)

def extend(base):
    """
    Can be used to extend a class.

    This is equivalent to creating methods and decorating each with the `addto` function.
    """
    def _wrapper(cls):
        for name, value in cls.__dict__.items():
            if name not in ('__module__', '__dict__', '__weakref__', '__doc__'):
                setattr(base, name, value)
        if cls.__doc__:
            base.__doc__ += '\n'+cls.__doc__
        return cls
    return _wrapper

def addto(*types):
    "add method to a class"
    def _wrapper(fcn):
        pots = classmethod, staticmethod, property
        prop = next((i for i in pots if i in types), None)
        for tpe in types:
            if tpe in pots:
                continue

            if hasattr(fcn, '__module__'):
                old = getattr(tpe, fcn.__name__, None)
                if old:
                    fcn = wraps(old)(fcn)

            if prop is None:
                setattr(tpe, getattr(fcn, 'fget', fcn).__name__, fcn)
            else:
                setattr(tpe, fcn.__name__, prop(fcn))
    return _wrapper

def addproperty(other, attr = 'display', prop = None, **args):
    """
    Adds the decorated class as a property to another.

        >>> class A:
        ...     pass
        >>> @addproperty(A, 'toto')
        ... class B:
        ...     "class doc for B"
        ...     def __init__(self, other):
        ...         self.other = other
        >>> a = A()
        >>> assert A.toto.__doc__ == "class doc for B"
        >>> assert isinstance(a.toto, B)
        >>> assert a.toto is not a.toto     # new instances on each call
        >>> assert a.toto.other is a
    """
    def _wrapper(cls):
        if args:
            prop = property(lambda self: cls(self, **args), doc = cls.__doc__)
        else:
            prop = property(cls, doc = cls.__doc__)

        setattr(other, attr, prop)
        return cls
    return _wrapper if prop is None else _wrapper(prop)
