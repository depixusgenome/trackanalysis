#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   abc              import ABC, abstractmethod
from   itertools        import chain, repeat

from   copy             import deepcopy

import numpy            as     np
from   IPython          import get_ipython # pylint: disable=import-error

from   utils.decoration import addto as _addto
hv    = sys.modules['holoviews']  # pylint: disable=invalid-name

def _display_hook(item):
    "displays an item"
    disp  = item.display()
    shell = get_ipython()
    if shell is not None:
        fmt   = shell.display_formatter.formatters['text/html']
        fcn   = fmt.lookup_by_type(type(disp))
        return fcn(disp)
    return disp

def displayhook(cls, *args):
    "Adds the class as a hook"
    shell = get_ipython()
    if shell is not None:
        fmt = shell.display_formatter.formatters['text/html']
        fmt.for_type(cls, _display_hook)
        for i in args:
            fmt.for_type(i, _display_hook)
    return cls

def addto(*types, addhook = 'auto'):
    "adds the item as a display hook"
    shell   = get_ipython()
    wrapper = _addto(*types)
    if shell is None:
        return wrapper

    fmt = shell.display_formatter.formatters['text/html']
    def _wrap(fcn):
        wrapper(fcn)
        if isinstance(fcn, property):
            name = getattr(fcn.fget, '__name__', None)
        else:
            name = getattr(fcn, '__name__', None)
        if (name == 'display' and addhook == 'auto') or addhook is True:
            for cls in types:
                fmt.for_type(cls, _display_hook)
    return _wrap

def addproperty(other, attr = 'display', prop = None, **args):
    "Adds the property to TracksDict"
    def _wrapper(cls):
        if args:
            prop = property(lambda self: cls(self, **args), doc = cls.__doc__)
        else:
            prop = property(cls, doc = cls.__doc__)

        setattr(other, attr, prop)
        return cls
    return _wrapper if prop is None else _wrapper(prop)

@displayhook
class BasicDisplay(ABC):
    "Everything needed for creating a dynamic map display"
    KEYWORDS = frozenset(locals())
    def __init__(self, items, **opts):
        self._items   = items
        for i in self.KEYWORDS:
            setattr(self, i, opts.pop(i[1:], getattr(self.__class__, i)))
        self._opts    = opts

    def __init_subclass__(cls, **args):
        for name, itm in args.items():
            if isinstance(itm, tuple):
                addproperty(itm[0], name, **itm[1], prop = cls)
            else:
                addproperty(itm, name, prop = cls)

    def __add__(self, other):
        return self.display() + (other if isinstance(other, hv.Element) else other.display())

    def __mul__(self, other):
        return self.display() * (other if isinstance(other, hv.Element) else other.display())

    def __lshift__(self, other):
        return self.display() << (other if isinstance(other, hv.Element) else other.display())

    def __rshift__(self, other):
        return self.display() >> (other if isinstance(other, hv.Element) else other.display())

    def config(self, name = ...):
        "returns the config"
        cnf = deepcopy(self._opts)
        cnf.update({i[1:]: deepcopy(j) for i, j in self.__dict__.items()
                    if (i not in ('_opts', '_items') and
                        len(i) > 2 and i[0] == '_'   and
                        i[1].lower() == i[1])})
        return cnf if name is Ellipsis else cnf[name]

    def __call__(self, **opts):
        default = self.__class__(self._items).config()
        config  = {i: j for i, j in self.config().items() if j != default[i]}
        config.update(opts)
        return self.__class__(self._items, **config)

    @staticmethod
    def concat(itr):
        "concatenates arrays, appending a NaN"
        return np.concatenate(list(chain.from_iterable(zip(itr, repeat([np.NaN])))))

    def display(self, **kwa):
        "displays the cycles using a dynamic map"
        this = self(**kwa) if kwa else self
        fcn  = this.getmethod()
        keys = this.getredim()
        if keys is None:
            return fcn()

        itr   = getattr(keys, 'items', lambda : keys)
        kdims = [i                      for i, _ in itr()]
        vals  = [(i, j)                 for i, j in itr() if isinstance(j, list)]
        rngs  = [(i, (j.start, j.stop)) for i, j in itr() if isinstance(j, slice)]
        done  = set(dict(vals)) | set(dict(rngs))
        sels  = [(i, [j])               for i, j in itr() if i not in done]
        return (hv.DynamicMap(fcn, kdims = kdims)
                .redim.values(**dict(vals), **dict(sels))
                .redim.range(**dict(rngs)))

    @abstractmethod
    def getmethod(self):
        "Returns the method used by the dynamic map"

    @abstractmethod
    def getredim(self):
        "Returns the keys used by the dynamic map"

__all__ = ['addto', 'displayhook']
