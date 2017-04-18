#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-ancestors
"all view aspects here"

import numpy as np
from bokeh.models.widgets.inputs  import (InputWidget, Callback, String,
                                          Float, Int, Instance)

from .base import BokehView

class IntInput(InputWidget):
    """ Single-line input widget. """
    __implementation__ = "intinput.coffee"

    value    = Int(default=0, help="Initial or entered int value")
    start    = Int(default=0, help="min value which can be input")
    step     = Int(default=1,  help="step value which can be input")
    end      = Int(default=10, help="max value which can be input")
    callback = Instance(Callback, help="""
    A callback to run in the browser whenever the user unfocuses the TextInput
    widget by hitting Enter or clicking outside of the text box area.
    """)
    placeholder = String(default="", help="Placeholder for empty input field")

class FloatInput(InputWidget):
    """ Single-line input widget. """
    __implementation__ = "floatinput.coffee"

    value    = Float(default=0.,  help="Initial or entered int value")
    start    = Float(default=0.,  help="min value which can be input")
    step     = Float(default=1.,  help="step value which can be input")
    end      = Float(default=10., help="max value which can be input")
    callback = Instance(Callback, help="""
    A callback to run in the browser whenever the user unfocuses the TextInput
    widget by hitting Enter or clicking outside of the text box area.
    """)
    placeholder = String(default="", help="Placeholder for empty input field")

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

class BeadInput(BokehView):
    "Spinner for controlling the current bead"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._ctrl.getGlobal('css').title.beadinput.default = 'Bead'
        self._ctrl.getGlobal('css').beadinput.defaults = {'width': 60, 'height' : 25}
        self.__beads = np.empty((0,), dtype = 'i4')
        self.__inp   = None

    def observe(self, doc): # pylint: disable=arguments-differ
        "Adds keypress for changin beads"
        self.getroots(doc)
        def _onproject(items):
            if 'track' in items:
                self.__beads        = np.sort(tuple(self.getbeads()))
                self.__inp.disabled = len(self.__beads) == 0
                if len(self.__beads):
                    self.__inp.start = self.__beads[0]
                    self.__inp.end   = self.__beads[-1]
                    self.__inp.value = self.__beads[0]

            elif 'bead' in items:
                self.__inp.value = items['bead'].value

        self._ctrl.getGlobal('project').observe(_onproject)

        self._keys.addKeyPress(('keypress.beadup',
                                lambda: self.__onchange_cb('', '', self.__inp.value+1)))
        self._keys.addKeyPress(('keypress.beaddown',
                                lambda: self.__onchange_cb('', '', self.__inp.value-1)))

    def getroots(self, _):
        "adds items to doc"
        kwa = dict(height       = self._ctrl.getGlobal('css', 'beadinput.height'),
                   width        = self._ctrl.getGlobal('css', 'beadinput.width'),
                   disabled     = True,
                   title        = self._ctrl.getGlobal('css').title.beadinput.get())
        self.__inp   = IntInput(**kwa)
        self.__inp.on_change("value", self.__onchange_cb)
        self.enableOnTrack(self.__inp)
        return self.__inp

    @property
    def input(self):
        "returns the bokeh model"
        return self.__inp

    def __onchange_cb(self, attr, old, new):
        if self.__inp.disabled:
            return

        if new not in self.__beads:
            new = self.__beads[min(len(self.__beads)-1,
                                   np.searchsorted(self.__beads, new))]

        if new == old:
            self.__inp.value = new
        else:
            with self.action:
                self._ctrl.getGlobal("project").bead.set(new)

    def getbeads(self):
        "returns the active beads"
        track = self._ctrl.track(self._ctrl.getGlobal("project").track.get())
        if track is None:
            return []
        return track.beadsonly.keys()
