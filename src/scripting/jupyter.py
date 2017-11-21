#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sets up jupyter stuff
"""
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

_configure_jupyter()
try:
    import holoviews as hv
except ImportError:
    raise RuntimeError("Missing holoviews")
else:
    # type: ignore
    _configure_hv()
    # pylint: disable=redefined-builtin,wildcard-import,unused-import,unused-variable
    # pylint: disable=redefined-outer-name,unused-wildcard-import
    import holoviews.operation  as hvops
    from data.__scripting__.holoviewing           import * # type: ignore
    from cleaning.__scripting__.holoviewing       import * # type: ignore
    from eventdetection.__scripting__.holoviewing import * # type: ignore
    from peakfinding.__scripting__.holoviewing    import * # type: ignore
    from peakcalling.__scripting__.holoviewing    import * # type: ignore
    from ramp.__scripting__.holoviewing           import * # type: ignore
    from .curve                                   import * # type: ignore

del _configure_jupyter, _configure_hv
