#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""

from IPython            import get_ipython
from utils.decoration   import addto as _addto

def _display_hook(item):
    "displays an item"
    disp = item.display()
    fmt  = get_ipython().display_formatter.formatters['text/html']
    fcn  = fmt.lookup_by_type(type(disp))
    return fcn(disp)

def displayhook(cls):
    "Adds the class as a hook"
    fmt = get_ipython().display_formatter.formatters['text/html']
    fmt.for_type(cls, _display_hook)
    return cls

def addto(*types, addhook = 'auto'):
    "adds the item as a display hook"
    wrapper = _addto(*types)
    def _wrap(fcn):
        wrapper(fcn)
        name = getattr(fcn, '__name__', None)
        if (name == 'display' and addhook == 'auto') or addhook is True:
            fmt = get_ipython().display_formatter.formatters['text/html']
            for cls in types:
                fmt.for_type(cls, _display_hook)
    return _wrap

__all__ = ['addto', 'displayhook']
