#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=import-error
"""
Add hv stuff
"""
from IPython         import get_ipython
from IPython.display import HTML, Markdown, display as _display
from .tasks          import Tasks, _DOCHelper # pylint: disable=protected-access

def display(self):
    "displays helpful doc"
    tpe = self.tasktype()
    _display(HTML(f'<H3> {str(self)}</H3>'
                  +f'<p>Its task is {tpe.__module__}.{tpe.__qualname__}</p>'
                  +'<H4>Description</H4>'
                  +'<p>'+' '.join(getattr(_DOCHelper, self.name).value)+'</p>'
                  +'<H4>Task documentation</H4>'))
    _display(Markdown(tpe.__doc__))
    return _display()

del Tasks.__repr__

def _setup():
    shell = get_ipython()
    fmt   = shell.display_formatter.formatters['text/html']
    fmt.for_type(Tasks, display)
_setup()


__all__: list = []
