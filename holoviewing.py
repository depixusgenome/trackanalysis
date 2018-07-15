#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
from   typing               import TypeVar, FrozenSet
from   abc                  import ABC, abstractmethod
from   itertools            import chain, repeat
from   copy                 import deepcopy


import numpy                as     np
import pandas               as     pd
import holoviews            as     hv                   # pylint: disable=import-error
from   IPython              import get_ipython          # pylint: disable=import-error
from   IPython.display      import display as _display  # pylint: disable=import-error

from   utils.decoration     import addto as _addto, addproperty
from   utils.attrdefaults   import setdefault

def _display_hook(item):
    "displays an item"
    if (type(item).__module__.startswith('holoviews')
            or isinstance(item, pd.DataFrame)):
        disp = item
    else:
        disp = item.display()

    if isinstance(disp, pd.DataFrame):
        _display(disp)
        return None

    if type(disp).__module__.startswith('holoviews'):
        return hv.ipython.display(disp)

    shell = get_ipython()
    if shell is not None:
        fmt = shell.display_formatter.formatters['text/html']
        fcn = fmt.lookup_by_type(type(disp))
        return fcn(disp)
    return disp

def displayhook(cls, *args):
    "Adds the class as a hook"
    shell = get_ipython()
    if shell is None:
        return cls

    fmt = shell.display_formatter.formatters['text/html']
    if isinstance(cls, type):
        fmt.for_type(cls, _display_hook)
        for i in args:
            fmt.for_type(i, _display_hook)
        return cls

    def _wrapper(itm):
        fmt.for_type(itm, lambda x: _display_hook(cls(x)))
        return itm
    return _wrapper

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
                if cls not in (property, classmethod, staticmethod):
                    fmt.for_type(cls, _display_hook)
    return _wrap

Self = TypeVar('Self', bound = 'ItemsDisplay')

@displayhook
class ItemsDisplay(ABC):
    "Everything needed for creating a dynamic map display"
    KEYWORDS: FrozenSet[str] = frozenset()
    def __init__(self, items, **opts):
        if isinstance(items, ItemsDisplay):
            opts, kwa   = items.config(minimal = True), opts
            opts.update(kwa)
            items       = getattr(items, '_items')
        self._items   = items
        for i in self.KEYWORDS:
            if i[:2] != '__':
                setdefault(self, i[1:], opts, fieldname = i)
        self._opts = {i: j for i, j in opts.items() if '_'+i not in self.KEYWORDS}

    def __init_subclass__(cls, **args):
        for name, itm in args.items():
            if isinstance(itm, tuple):
                addproperty(itm[0], name, cls, **itm[1])
            else:
                addproperty(itm, name, cls)

    def __add__(self, other):
        return self.display() + (other if isinstance(other, hv.Element) else other.display())

    def __mul__(self, other):
        return self.display() * (other if isinstance(other, hv.Element) else other.display())

    def __lshift__(self, other):
        return self.display() << (other if isinstance(other, hv.Element) else other.display())

    def __rshift__(self, other):
        return self.display() >> (other if isinstance(other, hv.Element) else other.display())

    def config(self, name = ..., minimal = False):
        "returns the config"
        if isinstance(name, str):
            return getattr(self, '_'+name) if hasattr(self, '_'+name) else self._opts[name]

        keys = {i for i in self.__dict__
                if (i not in ('_opts', '_items') and
                    len(i) > 2 and i[0] == '_'   and
                    i[1].lower() == i[1])}
        if minimal:
            keys -= {i for i in keys if getattr(self, i) == getattr(self.__class__, i)}

        cnf = deepcopy(self._opts) if self._opts or not minimal else {}
        cnf.update({i[1:]: deepcopy(getattr(self, i)) for i in keys})
        return cnf

    def __call__(self: Self, **opts) -> Self:
        default = self.__class__(self._items).config()
        config  = {i: j for i, j in self.config().items() if j != default[i]}
        config.update(opts)
        return self.__class__(self._items, **config)

    @abstractmethod
    def display(self, **kwa):
        "displays hv stuff"

    @staticmethod
    def concat(itr):
        "concatenates arrays, appending a NaN"
        return np.concatenate(list(chain.from_iterable(zip(itr, repeat([np.NaN])))))

class BasicDisplay(ItemsDisplay):
    "Everything needed for creating a dynamic map display"
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

def dropdown(options, fcn = None, layout = None, clear_output = True, **kwa):
    """
    creates a dropdown with all files as values and executes the
    provided method with that value:

    ```python
    # displays events for a selected file

    @dropdown
    def showevents(dropdown: ipywidgets.Dropdown):
        return TRACKS[dropdown.value].events
    ```
    """
    if fcn is None:
        return lambda x: dropdown(options, fcn = x, layout = layout, **kwa)

    import ipywidgets as widgets
    ddown = widgets.Dropdown(options = options, **kwa)
    out   = widgets.Output(layout = layout if layout else {})
    def _wrapped(value):
        if clear_output:
            out.clear_output()
        with out:
            cur = fcn(value)
            if cur is not None:
                _display(cur)

    ddown.observe(lambda ch: _wrapped(ch['new']), 'value')
    ddown.on_displayed(lambda x: _wrapped(x.value))
    return widgets.VBox([ddown, out])

__all__ = ['addto', 'displayhook', 'addproperty']
