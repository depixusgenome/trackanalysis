#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Basic bokeh models for dealing with it's idiosyncraties"
from itertools               import product
import re

from bokeh.models            import Row, Model, HoverTool, CustomJS, NumberFormatter
from bokeh.plotting.figure   import Figure

import bokeh.core.properties   as     props

def from_py_func(func, **kwa):
    """ Create a CustomJS instance from a Python function. The
    function is translated to Python using PyScript.
    """
    def _isgood(val):
        if isinstance(val, dict):
            return (all(isinstance(i, str) for i in val)
                    and all(_isgood(i) for i in val.items()))
        elif isinstance(val, (tuple, list)):
            val = list(val)
            return all(_isgood(i) for i in val)
        return isinstance(val, (float, int, str))

    cust = CustomJS.from_py_func(func)
    for name, val in kwa.items():
        assert _isgood(val)
        cust.code = re.sub(r'(\W)%s(\W)' % name,
                           # pylint: disable=cell-var-from-loop
                           lambda x: x.group(1)+repr(val)+x.group(2),
                           cust.code)
    return cust

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

        if plotter.css.responsive.get():
            kwa['sizing_mode'] = 'scale_width'
        else:
            kwa['sizing_mode'] = plotter.css.sizing_mode.get()

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

class DpxNumberFormatter(NumberFormatter):
    "Deals with"
    __implementation__ = """
    import {NumberFormatter, StringFormatter} from "models/widgets/cell_formatters"

    export class DpxNumberFormatter extends NumberFormatter
      type: 'DpxNumberFormatter'

      doFormat: (row, cell, value, columnDef, dataContext) ->
        if value or value == 0
            return super(row, cell, value, columnDef, dataContext)

        StringFormatter.prototype.doFormat.apply(this, [row, cell, null, columnDef, dataContext])
    """
