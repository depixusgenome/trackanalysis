#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"

try:
    from    bokeh.colors   import named as _bkclr
except ImportError:
    import  bokeh.colors   as _bkclr

def setcolors(mdl,**colors):
    "sets colors"
    colors = {i: '#6baed6' if j == 'blue' else j for i, j in colors.items()}
    mdl.css.colors.basic.defaults = colors
    mdl.css.colors.dark .defaults = colors

def getcolors(mdl):
    "returns the colors in hex format"
    colors = mdl.css.colors[mdl.css.theme.get()].getitems(...)
    return {i: tohex(j) for i, j in colors.items()}

def tohex(clr:str):
    "return the hex value"
    return clr if clr[0] == '#' else getattr(_bkclr, clr).to_hex()
