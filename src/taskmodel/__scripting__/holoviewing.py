#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=import-error
"""
Add hv stuff
"""
from IPython         import get_ipython
from IPython.display import Markdown, display as _display
from .tasks          import Tasks, _DOCHelper # pylint: disable=protected-access

def display(self):
    "displays helpful doc"
    tpe = self.tasktype()
    des = ' '.join(getattr(_DOCHelper, self.name).value)
    doc = f"""
          # {str(self)}
          Its task is `{tpe.__module__}.{tpe.__qualname__}`

          ## Description
          {des.capitalize()}

          ## `{tpe.__qualname__}` Documentation
          """.replace('\n          ', '\n').strip()+'\n'
    doc += tpe.__doc__.replace('\n    ', '\n').replace('\n#', '\n###')
    _display(Markdown(doc.strip()))
    return _display()

del Tasks.__repr__

def _setup():
    shell = get_ipython()
    fmt   = shell.display_formatter.formatters['text/html']
    fmt.for_type(Tasks, display)
_setup()


__all__: list = []
