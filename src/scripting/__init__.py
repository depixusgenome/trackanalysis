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
import version

# pylint: disable=wildcard-import, ungrouped-imports
from signalfilter                 import *
from model.__scripting__          import *
from app.__scripting__            import *
from data.__scripting__           import *
from cleaning.__scripting__       import *
from eventdetection.__scripting__ import *
from peakfinding.__scripting__    import *
from peakcalling.__scripting__    import * # type: ignore
from .parallel                    import parallel

LOGS = getLogger(__name__)

try:
    LOGS.info(f'version is {version.version()}')
except TypeError:
    LOGS.info(f'version is {version.version}')

try:
    from .curve                   import * # type: ignore
except ImportError:
    pass

_STACK = [i.filename for i in inspect.stack()]
def _is_jupyter():
    return any(i.endswith("ipykernel/zmqshell.py") for i in _STACK)

try:
    # pylint: disable=import-error
    import holoviews            as hv
    import holoviews.operation  as hvops
except ImportError:
    pass
else:
    # type: ignore
    from data.__scripting__.holoviewing           import * # pylint: disable=redefined-builtin
    from eventdetection.__scripting__.holoviewing import *
    from peakfinding.__scripting__.holoviewing    import *
    from peakcalling.__scripting__.holoviewing    import *
    from ramp.__scripting__.holoviewing           import *
    def _configure_hv():
        # pylint: disable=import-error,bare-except,unused-import,unused-variable
        exts = []
        try:
            import bokeh.io as _io
            _io.output_notebook()
            exts.append('bokeh')
        except:
            pass

        try:
            import matplotlib
            exts.append('matplotlib')
        except ImportError:
            pass

        if exts:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning, lineno = 6)
                hv.notebook_extension(*exts)
            del warnings

            if _is_jupyter():
                try:
                    from IPython import get_ipython
                    get_ipython().magic('output size=150')
                except:
                    pass

    _configure_hv()
    del _configure_hv

def _configure_jupyter():
    if not _is_jupyter():
        return

    # pylint: disable=import-error,bare-except
    try:
        from IPython              import get_ipython
        from IPython.core.display import display as _display, HTML
        if 'autoreload' not in get_ipython().extension_manager.loaded:
            get_ipython().magic('load_ext autoreload')
            get_ipython().magic('autoreload 2')
            get_ipython().magic('matplotlib inline')
        _display(HTML("<style>.container { width:100% !important; }</style>"))
    except:
        pass

_configure_jupyter()
del _configure_jupyter

def _test():
    if _is_jupyter():
        return
    stack  = [i for i in _STACK if 'importlib' not in i and i != '<stdin>']
    ends   = "IPython/core/magics/execution.py", "/trackanalysis.py"
    starts = ("<ipython-input",)
    if any(any(i.endswith(j) for j in ends) or any(i.startswith(j) for j in starts)
           for i in stack):
        return

    import traceback
    traceback.print_stack()
    assert False, stack[-1]
#_test()
del _test
del _is_jupyter
del _STACK
