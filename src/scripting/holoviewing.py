#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""

from IPython            import get_ipython
from utils.decoration   import addto as _addto

def _display_hook(item):
    "displays an item"
    disp  = item.display()
    shell = get_ipython()
    if shell is not None:
        fmt   = shell.display_formatter.formatters['text/html']
        fcn   = fmt.lookup_by_type(type(disp))
        return fcn(disp)
    return disp

def displayhook(cls):
    "Adds the class as a hook"
    shell = get_ipython()
    if shell is not None:
        fmt = shell.display_formatter.formatters['text/html']
        fmt.for_type(cls, _display_hook)
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

__all__ = ['addto', 'displayhook']
