#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
basic theme
"""
from utils import dflt, dataclass

DARK = {"Figure" : {"background_fill_color": "#20262B",
                    "border_fill_color": "#15191C",
                    "outline_line_color": "#E0E0E0",
                    "outline_line_alpha": 0.25},
        "Grid":    {"grid_line_color": "#E0E0E0",
                    "grid_line_alpha": 0.25},
        "Axis":    {"major_tick_line_color": "#E0E0E0",
                    "minor_tick_line_color": "#E0E0E0",
                    "axis_line_color": "#E0E0E0",
                    "major_label_text_color": "#E0E0E0",
                    "axis_label_text_color": "#E0E0E0"},
        "Legend":  {"label_text_color": "#E0E0E0",
                    "border_line_alpha": 0,
                    "background_fill_alpha": 0.25,
                    "background_fill_color": "#20262B"},
        "ColorBar":{"title_text_color": "#E0E0E0",
                    "major_label_text_color": "#E0E0E0",
                    "background_fill_color": "#15191C",
                    "bar_line_alpha": 0},
        "Title":   {"text_color": "#E0E0E0"}}

@dataclass
class MainTheme:
    """
    main theme
    """
    name        : str  = 'main'
    sizingmode  : str  = 'fixed'
    colorblue   : str  = '#6baed6'
    dark        : dict = dflt({"attrs": DARK})
    basic       : dict = dflt({})
    customdark  : dict = dflt({})
    customlight : dict = dflt({})
    themename   : str  = 'dark'

    @property
    def theme(self) -> dict:
        "return the current theme's json"
        return self[self.themename]

    def __getitem__(self, name):
        out = getattr(self, name, None)
        if out is None:
            import bokeh.themes as _theme
            if name in ('light', 'dark'):
                name += '_minimal'
            if hasattr(_theme, '_'+name):
                return getattr(_theme, '_'+name).json
            return self.dark
        return out
