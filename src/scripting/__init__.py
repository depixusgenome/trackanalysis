#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Used for scripting: something similar to matplotlib's pyplot.

We add some methods and change the default behaviour:

    * Track:

        * *__init__* takes *path* as it's first positional argument
        * an *events* property is added
        * a *rawprecision* method is added

    * Beads, Cycles:

        * can filter their output using *withfilter*

    * Beads, Cycles, Events:

        * *withcopy(True)* is called in the *__init__* by default
        * a *rawprecision* method is added
        * *with...* methods return an updated copy
"""
# pylint: disable=unused-import
from   itertools import chain, product, repeat
from   functools import wraps, partial
from   pathlib   import Path

import pickle                           # pylint: disable=unused-import
import inspect
import re
import numpy                 as np
import pandas                as pd

try:
    import matplotlib.pyplot as plt     # pylint: disable=import-error
except ImportError:
    pass

from data                         import Beads, Cycles
from eventdetection.processor     import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor        import PeakSelectorTask
from utils.logconfig              import getLogger
import sequences
import version

# pylint: disable=wildcard-import, ungrouped-imports
from signalfilter                 import *
from model.__scripting__          import * # type: ignore
from app.__scripting__            import * # type: ignore
from data.__scripting__           import * # type: ignore
from cleaning.__scripting__       import * # type: ignore
from eventdetection.__scripting__ import * # type: ignore
from peakfinding.__scripting__    import * # type: ignore
from peakcalling.__scripting__    import * # type: ignore
from .datadump                    import LazyShelf

_STACK = [i.filename for i in inspect.stack()]
_ISJUP = False

def _is_jupyter():
    return any(i.endswith("ipykernel/zmqshell.py") for i in _STACK)

def _test():
    stack  = [i for i in _STACK if 'importlib' not in i and i != '<stdin>']
    ends   = "IPython/core/magics/execution.py", "/trackanalysis.py"
    starts = ("<ipython-input",)
    if any(any(i.endswith(j) for j in ends) or any(i.startswith(j) for j in starts)
           for i in stack):
        return

    import traceback
    traceback.print_stack()
    assert False, stack[-1]

if _is_jupyter():
    try:
        from .jupyter import * # type: ignore # pylint: disable=redefined-builtin
    except ImportError:
        pass
    else:
        _ISJUP = True
else:
    _test()

try:
    getLogger(__name__).info(f'{version.version()}{" for jupyter" if _ISJUP else ""}')
except TypeError:
    getLogger(__name__).info(f'{version.version}{" for jupyter" if _ISJUP else ""}')

del _test, _is_jupyter, _STACK, _ISJUP
