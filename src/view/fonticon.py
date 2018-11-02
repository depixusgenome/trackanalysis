#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" A "stock" icon. """
import bokeh.core.properties      as     props
from   bokeh.models.widgets.icons import AbstractIcon
from   .static                    import ROUTE

class FontIcon(AbstractIcon): # pylint: disable=too-many-ancestors
    """
    A "stock" icon from those available in static/icons.css
    """
    __implementation__ = "fonticon.coffee"
    __css__            = ROUTE+"/icons.css?v=gittag"
    name               = props.String("cog")
