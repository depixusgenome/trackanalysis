#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Bokeh toolbar model"
import bokeh.core.properties   as props
from   bokeh.models         import Widget

from   view.static          import route

class DpxDAQToolbar(Widget):
    "Toolbar model"
    __css__            = route("view.css")
    __javascript__     = route()
    __implementation__ = '_daqtoolbar.coffee'
    protocol    = props.String("manual")
    recording   = props.Bool(False)
    manual      = props.Int(-1)
    ramp        = props.Int(-1)
    probing     = props.Int(-1)
    record      = props.Int(-1)
    stop        = props.Int(-1)
    quit        = props.Int(-1)
    network     = props.Int(-1)
    message     = props.String("")
    hasquit     = props.Bool(False)
    zmagmin     = props.Float(0.)
    zmag        = props.Float(.5)
    zmagmax     = props.Float(1.)
    zinc        = props.Float(.1)
    speedmin    = props.Float(0.125)
    speed       = props.Float(.125)
    speedmax    = props.Float(1.)
    speedinc    = props.Float(.1)
    def __init__(self, **kwa):
        super().__init__(name = 'Main:toolbar', **kwa)
