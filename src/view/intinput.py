#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all view aspects here"

import numpy as np
from bokeh.models.widgets.inputs    import InputWidget, Callback, String, Int, Instance

from .base import BokehView

class IntInput(InputWidget):
    """ Single-line input widget. """
    __implementation__ = "intinput.coffee"

    value    = Int(default=0, help="Initial or entered int value")
    minvalue = Int(default=0, help="min value which can be input")
    maxvalue = Int(default=10, help="max value which can be input")
    callback = Instance(Callback, help="""
    A callback to run in the browser whenever the user unfocuses the TextInput
    widget by hitting Enter or clicking outside of the text box area.
    """)
    placeholder = String(default="", help="Placeholder for empty input field")

class BeadInput(BokehView):
    u"Spinner for controlling the current bead"
    def __init__(self, **kwa):
        u"Sets up the controller"
        super().__init__(**kwa)
        self.__beads = np.empty((0,), dtype = 'i4')

        kwa = dict(height       = self._ctrl.getGlobal('css', 'button.height'),
                   width        = 90,#self._ctrl.getGlobal('css', 'button.height'),
                   disabled     = True,
                   title        = 'bead number')
        self.__inp   = IntInput(**kwa)
        self.__inp.on_change("value", self._onchange_cb)
        self._ctrl.observe("globals.current", self._onUpdateCurrent)

    def getroots(self):
        u"adds items to doc"
        assert False

    @property
    def input(self):
        u"returns the bokeh model"
        return self.__inp

    def _onchange_cb(self, attr, old, new):
        if new not in self.__beads:
            new = self.__beads[min(len(self.__beads)-1,
                                   np.searchsorted(self.__beads, new))]
            self.__inp.value = new

        self._ctrl.getGlobal("current").bead = new

    def _onUpdateCurrent(self, **items):
        if 'track' in items:
            disabled = items['track'].value is items['empty']
            self.__inp.disabled = disabled
            if not disabled:
                beads = self._ctrl.track(items['track'].value).beadsonly.keys()
                self.__beads = np.sort(tuple(beads))
                self.__inp.minvalue = self.__beads[0]
                self.__inp.maxvalue = self.__beads[-1]
        elif 'bead' in items:
            self.__inp.value = items['bead'].value
