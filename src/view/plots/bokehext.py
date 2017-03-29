#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Basic bokeh models for dealing with it's idiosyncraties"
from types      import FunctionType
from itertools  import product

import flexx.pyscript        as     pyscript
from bokeh.models            import Row, Model, HoverTool, Model, CustomJS
from bokeh.plotting.figure   import Figure

import  bokeh.core.properties   as     props

def from_py_func(func):
    """ Create a CustomJS instance from a Python function. The
    function is translated to Python using PyScript.
    """
    if not isinstance(func, FunctionType):
        raise ValueError('CustomJS.from_py_func needs function object.')

    # Collect default values
    default_values = func.__defaults__  # Python 2.6+
    default_names  = func.__code__.co_varnames[:len(default_values)]
    args = dict(i for i in zip(default_names, default_values) if isinstance(i[1], Model))

    # Get JS code, we could rip out the function def, or just
    # call the function. We do the latter.
    code = pyscript.py2js(func, 'cb') + 'cb(%s);\n' % ', '.join(args)
    return CustomJS(code=code, args=args)

class DpxKeyedRow(Row):
    "define div with tabIndex"
    fig                = props.Instance(Figure)
    toolbar            = props.Instance(Model)
    keys               = props.Dict(props.String, props.String, help = 'keys and their action')
    zoomrate           = props.Float()
    panrate            = props.Float()
    __implementation__ = 'keyedrow.coffee'
    def __init__(self, plotter, fig, **kwa):
        vals = ('.'.join(i) for i in product(('pan', 'zoom'), ('x', 'y'), ('low', 'high')))
        cnf   = plotter.config.keypress

        keys  = dict((cnf[key].get(), key) for key in vals)
        keys[cnf.reset.get()] = 'reset'
        keys.update({cnf[tool].activate.get(): tool for tool in ('pan', 'zoom')})

        kwa.setdefault('sizing_mode', 'stretch_both')
        children = kwa.pop('children', [fig])
        super().__init__(children = children,
                         fig      = fig,
                         keys     = keys,
                         zoomrate = cnf.zoom.rate.get(),
                         panrate  = cnf.pan.rate.get(),
                         **kwa)

class DpxHoverTool(HoverTool):
    "sorts indices before displaying tooltips"
    maxcount           = props.Int(5)
    __implementation__ = """
    import * as p  from "core/properties"
    import {HoverTool, HoverToolView} from "models/tools/inspectors/hover_tool"

    export class DpxHoverToolView extends HoverToolView
        _update: (indices, tool, renderer, ds, {geometry}) ->
            inds = indices['1d'].indices
            if inds?.length > 1
                inds.sort((a,b) => a - b)
                if inds.length > @model.maxcount
                    ind = Math.floor((inds.length - @model.maxcount)*0.5)
                    indices['1d'].indices = inds.slice(ind, ind+@model.maxcount)
            super(indices, tool, renderer, ds, {geometry})

    export class DpxHoverTool extends HoverTool
        default_view: DpxHoverToolView
        @define { maxcount: [ p.Int, 5] }
    """
