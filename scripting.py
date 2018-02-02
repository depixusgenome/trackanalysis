#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Used for scripting: something similar to matplotlib's pyplot.
"""
import sys
# pylint: disable=unused-import
from   itertools import chain, product, repeat
from   functools import wraps, partial
from   pathlib   import Path

import pickle
import inspect
import re
import numpy                 as np
import pandas                as pd

try:
    import matplotlib.pyplot as plt     # pylint: disable=import-error
except ImportError:
    pass

_STACK = [i.filename for i in inspect.stack()]
ISJUP  = False

def _isjupyter() -> bool:
    "whether the import occurs from a jupyter session"
    return (any(i.endswith("ipykernel/zmqshell.py") for i in _STACK)
            or sys.modules.get('ACCEPT_SCRIPTING', '') == 'jupyter')


def test():
    "tests whether the import occurs from jupyter or ipython"
    if 'ACCEPT_SCRIPTING' in sys.modules or 'pudb' in sys.modules:
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

def _configure_hv(hvmod):
    # pylint: disable=import-error,bare-except,unused-import,unused-variable
    exts = []
    try:
        import bokeh.io as _io
        _io.output_notebook()
        exts.append('bokeh')
    except:
        pass

    if 'matplotlib.pyplot' in sys.modules:
        exts.append('matplotlib')

    if exts:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning, lineno = 6)
            hvmod.notebook_extension(*exts)
        del warnings

        try:
            from IPython import get_ipython
            get_ipython().magic('output size=150')
        except:
            pass

def _configure_jupyter():
    # pylint: disable=import-error,bare-except
    try:
        from IPython              import get_ipython
        shell = get_ipython()
        if 'autoreload' not in shell.extension_manager.loaded:
            shell.magic('load_ext autoreload')
            shell.magic('autoreload 2')
            shell.magic('matplotlib inline')

            from IPython.core.display import display as _display, HTML
            _display(HTML("<style>.container { width:100% !important; }</style>"))
    except:
        pass

def importlibs(locs, *names):
    "imports the relative jupyter package"
    import importlib
    for name in names:
        args = name if isinstance(name, tuple) else (name,) # type: tuple
        mod  = importlib.import_module(*args[:2])           # type: ignore
        allv = getattr(mod, '__all__') if len(args) < 3 else args[2]
        locs.update({i: getattr(mod, i) for i in allv})

def importjupyter(locs, *names):
    "imports the relative jupyter package"
    if _isjupyter():
        try:
            import holoviews as hv
            import holoviews.operation  as hvops
        except ImportError:
            return

        global ISJUP # pylint: disable=global-statement
        ISJUP         = True
        locs['hv']    = hv
        locs['hvops'] = hvops

        _configure_hv(hv)
        _configure_jupyter()
        importlibs(locs, *names)
    else:
        test()

def run(locs, direct, star, jupyter):
    "imports all modules"
    from .logconfig  import getLogger
    import version
    import importlib
    locs.update({i: importlib.import_module(i) for i in direct})
    importlibs   (locs, *star)
    importjupyter(locs, *jupyter)

    if getattr(locs.get('run', None), '__module__', None) == __name__:
        locs.pop('run')

    getLogger("").info(f'{version.version()}{" for jupyter" if ISJUP else ""}')
    if 'TUTORIAL' in locs:
        if _isjupyter():
            def tutorial():
                "clues for the beginner"
                from IPython.display import display, Markdown
                display(Markdown(locs['TUTORIAL']))
            locs['tutorial'] = tutorial
        else:
            def tutorial():
                "clues for the beginner"
                print(locs['TUTORIAL'])
            locs['tutorial'] = tutorial()

        getLogger("").info('Beginners can start by typing: tutorial()')

__all__ = tuple(i for i in locals()
                if (i not in {'isjupyter', 'run', 'test', 'importlibs', 'importjupyter', 'ISJUP'}
                    and i[0] != '_'))
