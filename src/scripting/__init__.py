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
import inspect
import numpy                 as np
import pandas                as pd
try:
    import matplotlib.pyplot as plt     # pylint: disable=import-error
except ImportError:
    pass

from data                       import Beads, Cycles
from eventdetection.processor   import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor      import PeakSelectorTask

# pylint: disable=wildcard-import
from signalfilter               import *
from model.task                 import *
from .track                     import *
from .scriptapp                 import *
try:
    from .curve                 import *
except ImportError:
    pass
try:
    from .holoviewing           import *
except ImportError:
    pass

_frame = None
for _frame in inspect.stack()[1:]:
    if 'importlib' not in _frame.filename:
        assert (_frame.filename == '<stdin>'
                or _frame.filename.startswith('<ipython'))
        break
del _frame

if 'ipykernel_launcher' in inspect.stack()[-3].filename:
    try:
        from IPython import get_ipython
        get_ipython().magic('load_ext autoreload')
        get_ipython().magic('autoreload 2')
        get_ipython().magic('matplotlib inline')
    except:                                         # pylint: disable=bare-except
        pass
