#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=broad-except
"""
Used for scripting: something similar to matplotlib's pyplot.
"""
import sys
import inspect

locals().update({i: getattr(__import__('functools'), i)
                 for i in ('partial', 'wraps')})
locals().update({i: getattr(__import__('itertools'), i)
                 for i in ('chain', 'product', 'repeat')},
                re      = __import__('re'),
                pickle  = __import__('pickle'),
                np      = __import__('numpy'),
                pd      = __import__('pandas'),
                Path    = __import__('pathlib').Path
               )
try:
    locals()['plt'] = __import__('matplotlib.pyplot')
except ImportError:
    pass

_STACK = [i.filename for i in inspect.stack()]
ISJUP  = [False]

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

def _configure_hv(hvmod, locs):
    exts = []
    try:
        __import__('bokeh.io').io.output_notebook()
        exts.append('bokeh')
    except Exception:
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
            import holoviews  as     hv
            __import__('IPython').get_ipython().magic('output size=150')

            opts  = locs.get("HV_OPTS", {})
            width = opts.get("width", 700)
            bcolor= opts.get("box_color", "lightblue")
            for i in opts.get("elements", ('Curve', 'Scatter', 'Distribution',
                                           'Spikes', 'Points', 'BoxWhisker',
                                           'Histogram', 'RGB', 'HeatMap', 'Image')):
                string = f"{i} [width={width}] {{+framewise}}"
                if i == 'BoxWhisker':
                    string = string.replace("]",  f"] (box_color='{bcolor}') ")
                hv.opts(string)
            hv.opts(f'Table[width={width}]')
        except Exception:
            pass

def _configure_jupyter():
    try:
        shell = __import__('IPython').get_ipython()
        if 'autoreload' not in shell.extension_manager.loaded:
            shell.magic('load_ext autoreload')
            shell.magic('autoreload 2')
            shell.magic('matplotlib inline')

            _display = __import__('IPython.core.display').core.display.display
            html     = __import__('IPython.core.display').core.display.HTML
            _display(html("<style>.container { width:100% !important; }</style>"))
    except Exception:
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
            from .holoviewing import dropdown
        except ImportError:
            return

        ISJUP[0]      = True
        locs['hv']    = hv
        locs['hvops'] = hvops
        locs['dropdown'] = dropdown

        _configure_hv(hv, locs)
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

    getLogger("").info('%s%s', version.version(), " for jupyter" if ISJUP[0] else "")
    if 'TUTORIAL' in locs:
        if _isjupyter():
            def tutorial():
                "clues for the beginner"
                display = __import__('IPython.display').display
                mkdown  = __import__('IPython.display').Markdown
                display(mkdown(locs['TUTORIAL']))
            locs['tutorial'] = tutorial
        else:
            def tutorial():
                "clues for the beginner"
                # mark the print as non-debug: add file = ...
                print(locs['TUTORIAL'], file = sys.stdout)
            locs['tutorial'] = tutorial

        getLogger("").info('Beginners can start by typing: tutorial()')

__all__ = tuple(i for i in locals()
                if (i not in {'isjupyter', 'run', 'test', 'importlibs', 'importjupyter', 'ISJUP'}
                    and i[0] != '_'))
