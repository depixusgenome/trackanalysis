#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"decoration utils"

import  pathlib
from    contextlib import contextmanager
from    functools  import wraps
from    typing     import Union, IO
from    inspect    import signature, isgeneratorfunction
import  numpy as np

StreamUnion = Union[str,pathlib.Path,IO]

def fromstream(streamopts):
    u"""
    wraps a method using a stream as input so it can use str, Path or stream

    The stream attribute will be identified as:
    1. the first one named *stream* or *path*
    2. the first which is **not** named *self* or *cls*
    """
    def _wrapper(fcn):
        bad        = {'self', 'cls', 'mcs'}
        good       = {'path', 'stream'}
        sig        = signature(fcn).parameters
        ind, first = next((i for i in enumerate(sig) if i[1] in good),
                          next((i for i in enumerate(sig) if i[1] not in bad),
                               (0, next(iter(sig)))))
        if isgeneratorfunction(fcn):
            @wraps(fcn)
            def _wrapgen(*args, **kwa):
                path = args[ind]
                if isinstance(path, pathlib.Path):
                    path = str(path)

                if isinstance(path, str):
                    with open(path, streamopts) as stream:
                        args = args[:ind] + (stream,) + args[ind+1:]
                        yield from fcn(*args, **kwa)
                else:
                    args = args[:ind] + (path,) + args[ind+1:]
                    yield from fcn(*args, **kwa)

            _wrapgen.__annotations__[first] = StreamUnion
            return _wrapgen
        else:
            @wraps(fcn)
            def _wrapfcn(*args, **kwa):
                path = args[ind]
                if isinstance(path, pathlib.Path):
                    path = str(path)

                if isinstance(path, str):
                    with open(path, streamopts) as stream:
                        args = args[:ind] + (stream,) + args[ind+1:]
                        return fcn(*args, **kwa)
                else:
                    args = args[:ind] + (path,) + args[ind+1:]
                    return fcn(*args, **kwa)

            _wrapfcn.__annotations__[first] = StreamUnion
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
