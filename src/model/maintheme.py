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
        "Axis":    {"major_tick_line_alpha": 0,
                    "major_tick_line_color": "#E0E0E0",

                    "minor_tick_line_alpha": 0,
                    "minor_tick_line_color": "#E0E0E0",

                    "axis_line_alpha": 0,
                    "axis_line_color": "#E0E0E0",

                    "major_label_text_color": "#E0E0E0",
                    "major_label_text_font": "Helvetica",
                    "major_label_text_font_size": "1.025em",

                    "axis_label_standoff": 10,
                    "axis_label_text_color": "#E0E0E0",
                    "axis_label_text_font": "Helvetica",
                    "axis_label_text_font_size": "1.25em",
                    "axis_label_text_font_style": "normal"},
        "Legend":  {"spacing": 8,
                    "glyph_width": 15,

                    "label_standoff": 8,
                    "label_text_color": "#E0E0E0",
                    "label_text_font": "Helvetica",
                    "label_text_font_size": "1.025em",

                    "border_line_alpha": 0,
                    "background_fill_alpha": 0.25,
                    "background_fill_color": "#20262B"},
        "ColorBar":{"title_text_color": "#E0E0E0",
                    "title_text_font": "Helvetica",
                    "title_text_font_size": "1.025em",
                    "title_text_font_style": "normal",

                    "major_label_text_color": "#E0E0E0",
                    "major_label_text_font": "Helvetica",
                    "major_label_text_font_size": "1.025em",

                    "background_fill_color": "#15191C",
                    "major_tick_line_alpha": 0,
                    "bar_line_alpha": 0},
        "Title":   {"text_color": "#E0E0E0",
                    "text_font": "Helvetica",
                    "text_font_size": "1.15em"}}

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
            return getattr(_theme, '_'+name).json
        return out
