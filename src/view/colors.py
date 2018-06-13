#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view for cleaning data"
from typing import Dict, Any, Union

try:
    from    bokeh.colors   import named as _bkclr
except ImportError:
    import  bokeh.colors   as _bkclr

def tohex(clr:Union[Dict[Any,str], str]):
    "return the hex value"
    if isinstance(clr, dict):
        return {i: tohex(j) for i, j in clr.items()}
    return clr if len(clr) > 0 and clr[0] == '#' else getattr(_bkclr, clr).to_hex()
