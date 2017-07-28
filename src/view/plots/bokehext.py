#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Basic bokeh models for dealing with it's idiosyncraties"
from itertools               import product
import re

from    bokeh                   import layouts
from    bokeh.models            import (Row, Model, HoverTool, CustomJS,
                                        NumberFormatter, ToolbarBox)
from    bokeh.plotting.figure   import Figure
import  bokeh.core.properties   as     props

from    ..base                  import defaultsizingmode

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

class DpxKeyedRow(Row): # pylint: disable=too-many-ancestors
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

        children = kwa.pop('children', [fig])
        super().__init__(children = children,
                         fig      = fig,
                         keys     = keys,
                         zoomrate = cnf.zoom.rate.get(),
                         panrate  = cnf.pan.rate.get(),
                         **defaultsizingmode(plotter, kwa))
    @classmethod
    def keyedlayout(cls, plot, main, *figs, bottom = None, left = None, right = None):
        "sets up a DpxKeyedRow layout"
        assert left is None or right is None
        kwa = plot.defaultsizingmode()
        if len(figs) == 0:
            keyed = cls(plot, main)
        else:
            figs  = (main,) + figs
            plts  = layouts.gridplot([[*figs]], **kwa,
                                     toolbar_location = plot.css.toolbar_location.get())

            keyed = cls(plot, main,
                        children = [plts],
                        toolbar  = next(i for i in plts.children if isinstance(i, ToolbarBox)),
                        **kwa)

        if {left, right, bottom} == {None}:
            return keyed

        if {left, right} == {None}:
            return layouts.column([keyed, bottom], **kwa)

        if {bottom, right} == {None}:
            return layouts.row([left, keyed], **kwa)

        if {bottom, left} == {None}:
            return layouts.row([keyed, right], **kwa)

        if left is None:
            return layouts.column([layouts.column([keyed, bottom], **kwa), right], **kwa)

        return layouts.column([left, layouts.column([keyed, bottom], **kwa)], **kwa)

class DpxHoverTool(HoverTool): # pylint: disable=too-many-ancestors
    "sorts indices before displaying tooltips"
    maxcount           = props.Int(5)
    __implementation__ = "hovertool.coffee"

class DpxNumberFormatter(NumberFormatter): # pylint: disable=too-many-ancestors
    "Deals with Nones correctly"
    __implementation__ = "numberformatter.coffee"
