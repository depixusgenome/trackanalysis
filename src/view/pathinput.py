#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-ancestors
"all view aspects here"

from bokeh.models.widgets.inputs  import (InputWidget, Callback, String,
                                          Int, Instance)

class PathInput(InputWidget):
    """ widget to access a path. """
    __implementation__ = "pathinput.coffee"
    value       = String(default="", help="""
    Initial or entered text value.
    """)
    callback    = Instance(Callback, help="""
    A callback to run in the browser whenever the user unfocuses the TextInput
    widget by hitting Enter or clicking outside of the text box area.
    """)
    placeholder = String(default="", help="Placeholder for empty input field")
    click       = Int(default = 0)
