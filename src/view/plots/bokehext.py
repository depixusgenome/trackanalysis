#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Basic bokeh models for dealing with it's idiosyncraties"
from itertools               import product

from    bokeh                   import layouts
from    bokeh.models            import (Row, Model, HoverTool,
                                        NumberFormatter, ToolbarBox)
from    bokeh.plotting.figure   import Figure
import  bokeh.core.properties   as     props

from    ..base                  import defaultsizingmode

class DpxKeyedRow(Row): # pylint: disable=too-many-ancestors
    "define div with tabIndex"
    fig                = props.Instance(Figure)
    toolbar            = props.Instance(Model)
    keys               = props.Dict(props.String, props.String, help = 'keys and their action')
    zoomrate           = props.Float()
    panrate            = props.Float()
    __implementation__ = 'keyedrow.coffee'
    def __init__(self, ctrl, plotter, fig, **kwa):
        vals  = (''.join(i) for i in product(('pan', 'zoom'), ('x', 'y'), ('low', 'high')))
        mdl   = ctrl.theme.model('keystroke')
        keys  = dict((mdl[key], key) for key in vals)
        keys[mdl['reset']] = 'reset'
        keys.update({mdl[tool+'activate']: tool for tool in ('pan', 'zoom')})

        children = kwa.pop('children', [fig])
        super().__init__(children = children,
                         fig      = fig,
                         keys     = keys,
                         zoomrate = mdl['zoomrate'],
                         panrate  = mdl['panrate'],
                         **defaultsizingmode(plotter, kwa, ctrl = ctrl))
    @classmethod
    def keyedlayout(cls, ctrl, plot, main, *figs, bottom = None, left = None, right = None):
        "sets up a DpxKeyedRow layout"
        assert left is None or right is None
        kwa = plot.defaultsizingmode()
        if len(figs) == 0:
            keyed = cls(ctrl, plot, main)
        else:
            figs  = (main,) + figs
            plts  = layouts.gridplot([[*figs]], **kwa,
                                     toolbar_location = plot.css.toolbar_location.get())

            # pylint: disable=not-an-iterable
            tbar  = next(i for i in plts.children if isinstance(i, ToolbarBox))
            keyed = cls(ctrl, plot, main, children = [plts], toolbar  = tbar, **kwa)

        if {left, right, bottom} == {None}:
            return keyed

        if {left, right} == {None}:
            return layouts.column([keyed, bottom], **kwa)

        if {bottom, right} == {None}:
            return layouts.row([left, keyed], **kwa)

        if {bottom, left} == {None}:
            return layouts.row([keyed, right], **kwa)

        if left is None:
            return layouts.row([layouts.column([keyed, bottom], **kwa), right], **kwa)

        return layouts.row([left, layouts.column([keyed, bottom], **kwa)], **kwa)

class DpxHoverTool(HoverTool): # pylint: disable=too-many-ancestors
    "sorts indices before displaying tooltips"
    maxcount           = props.Int(5)
    __implementation__ = "hovertool.coffee"

class DpxNumberFormatter(NumberFormatter): # pylint: disable=too-many-ancestors
    "Deals with Nones correctly"
    __implementation__ = "numberformatter.coffee"
