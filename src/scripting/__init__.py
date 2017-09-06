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

# pylint: disable=wildcard-import, ungrouped-imports
from signalfilter                 import *
from model.__scripting__          import *
from app.__scripting__            import *
from data.__scripting__           import *
from eventdetection.__scripting__ import *
from peakfinding.__scripting__    import *
from peakcalling.__scripting__    import *

try:
    from .curve                   import *
except ImportError:
    pass
try:
    import holoviews            as hv       # pylint: disable=import-error
    import holoviews.operation  as hvops    # pylint: disable=import-error
except ImportError:
    pass
else:
    from data.__holoviewing__               import * # pylint: disable=redefined-builtin
    from eventdetection.__holoviewing__     import *
    from peakfinding.__holoviewing__        import *
    from peakcalling.__holoviewing__        import *
    if 'ipykernel_launcher' in inspect.stack()[-3].filename:
        try:
            import bokeh.io as _io
            _io.output_notebook()
            hv.notebook_extension('bokeh')
            from IPython import get_ipython  # pylint: disable=import-error
            get_ipython().magic('output size=150')
        except:                              # pylint: disable=bare-except
            pass

if 'ipykernel_launcher' in inspect.stack()[-3].filename:
    try:
        from IPython              import get_ipython   # pylint: disable=import-error
        get_ipython().magic('load_ext autoreload')
        get_ipython().magic('autoreload 2')
        get_ipython().magic('matplotlib inline')

        from IPython.core.display import display, HTML # pylint: disable=import-error
        display(HTML("<style>.container { width:100% !important; }</style>"))
    except:                              # pylint: disable=bare-except
        pass

def _test():
    stack = [i.filename for i in inspect.stack()[1:]
             if 'importlib' not in i.filename and i.filename != '<stdin>']
    if any(i.endswith("IPython/core/magics/execution.py")
           for i in stack):
        return

    if any(i.endswith("ipykernel/zmqshell.py")
           for i in stack):
        return

    last = next((i for i in stack
                 if not (i.startswith('<ipython')
                         or i.endswith('/trackanalysis.py')
                         or 'ipython/extensions' in i)), None)
    if last is not None:
        import traceback
        traceback.print_stack()
        assert False, last
_test()
del _test
