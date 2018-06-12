#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
basic theme
"""
from utils import initdefaults

class MainTheme:
    """
    main theme
    """
    name        = 'main'
    sizingmode  = 'fixed'
    colorblue   = '#6baed6'
    dark        = {'attrs': {'Figure': {'background_fill_color':  '#2F2F2F',
                                        'border_fill_color':      '#2F2F2F',
                                        'outline_line_color':     '#444444' },
                             'Axis':   {'axis_line_color':        "white",
                                        'axis_label_text_color':  "white",
                                        'major_label_text_color': "white",
                                        'major_tick_line_color':  "white",
                                        'minor_tick_line_color':  "white"},
                             'Title':  {'text_color':             "white"}
                            }
                  }
    basic: dict = {}
    themename   = 'dark'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @property
    def theme(self) -> dict:
        "return the current theme's json"
        return getattr(self, self.themename, {})
