#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Creates a dataframe"

from   typing    import Dict, Callable, Any, Iterator, Tuple, KeysView
from   functools import partial
import re
import shelve

class _DEFAULT:
    pass

class LazyShelf(dict):
    """
    Lazy shelf

    This works as a dictionnary where values are provided as functions in order
    to allow for lazy instantiation. Once computed, values are stored on the
    hardrive such that no execution will be required again.
    """
    __slots__ = 'path', 'info'
    def __init__(self, path: str, *args, **kwa) -> None:
        super().__init__()
        self.path = path
        self.info: Dict[Any, Callable[[], Any]] = {}
        self.update(*args, **kwa)

    def get(self, key, default = None):
        "returns the value"
        val = self.info.get(key, default)
        return val() if isinstance(val, partial) else val

    def __contains__(self, key) -> bool:
        "returns the value"
        return key in self.info

    def __getitem__(self, key):
        "returns the value"
        val = self.info[key]
        return val() if isinstance(val, partial) else val

    def __setitem__(self, key, value):
        self.info[key] = partial(self.__store, key, value) if callable(value) else value

    def __call__(self, name = None):
        """
        Decorator for storing a new item.

        The key name is either specified in the decorator or parsed from the
        function name. The regex `^_(compute)*_*` is stripped from the function name.

        ```python
        SHELF = LazyShelf("/tmp")

        @SHELF
        def _compute_mykey():
            pass
        assert 'mykey' in SHELF

        @SHELF
        def _mykey2():
            pass
        assert 'mykey2' in SHELF

        @SHELF
        def mykey3():
            pass
        assert 'mykey3' in SHELF

        @SHELF('mykey4')
        def whatever():
            pass
        assert 'mykey4' in SHELF
        ```
        """
        if isinstance(name, str):
            def _wrapper(fcn):
                self[name] = fcn
                return fcn
            return _wrapper

        match = re.match('^_*(?:compute)*_*(.*)', name.__name__)
        self[match.group(1) if match else name.__name__] = name
        return name

    def set(self, key,  # pylint: disable=keyword-arg-before-vararg
            value = _DEFAULT, force = False, *args, **kwa):
        "sets and returns the value"
        if value is _DEFAULT:
            key, value = value.__name__, value
            if key[0] == '_':
                key = key[1:]

        if force:
            self.pop(key, None)
        if callable(value):
            return self.__store(key, value, *args, **kwa)
        self.info[key] = value
        return value

    def setdefault(self, key, value, *args, **kwa):
        "sets if not set"
        if callable(value):
            self.info.setdefault(key, partial(self.__store,  key, value, *args, **kwa))
        else:
            self.info.setdefault(key, value)

    def update(self, *args, **kwa):
        "updates the dictionnary"
        info = dict(*args, **kwa)
        for i, j in info.items():
            self.info[i] = partial(self.__store, i, j) if callable(j) else j

    def pop(self, key, default = _DEFAULT):
        "pops value"
        with shelve.open(self.path) as stream:
            if key in stream:
                del stream[key]

        val = self.info.pop(key, _DEFAULT) if default is _DEFAULT else self.info.pop(key, default)
        return val

    __delitem__ = pop

    def isstored(self, key) -> bool:
        "returns the value"
        with shelve.open(self.path) as stream:
            return key in stream.keys()

    def keys(self) -> KeysView:
        "returns keys"
        return self.info.keys()

    def items(self) -> Iterator[Tuple[Any, Any]]: # type: ignore
        "returns keys"
        with shelve.open(self.path) as stream:
            for i, val in list(self.info.items()):
                if i in stream:
                    val          = stream[i]
                    self.info[i] = val
                else:
                    val          = val()
                    stream[i]    = val
                    self.info[i] = val
                yield (i, val)

    def values(self) -> Iterator:                 # type: ignore
        "returns keys"
        return (i for _, i in self.items())

    def store(self, key, value = _DEFAULT):
        "stores a value"
        if value is _DEFAULT:
            key, value = value.__name__, value
            if key[0] == '_':
                key = key[1:]

        with shelve.open(self.path) as stream:
            stream[key] = self.info[key] = value
        return value

    def __store(self, key, fcn: Callable, *args, **kwa):
        with shelve.open(self.path) as stream:
            if key in stream:
                val            = stream[key]
                self.info[key] = val
            else:
                val            = fcn(*args, **kwa)
                stream[key]    = val
                self.info[key] = val
        return val

__all__ = ["LazyShelf"]
