#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=too-many-ancestors
"all view aspects here"

import re
import numpy as np
from bokeh.models.widgets.inputs  import (InputWidget, Callback, String,
                                          Float, Int, Instance)

from model.task import DiscardedBeadsTask
from .base import BokehView

class DpxIntInput(InputWidget):
    """ Single-line input widget. """
    __implementation__ = "intinput.coffee"

    value    = Int(default=0, help="Initial or entered int value")
    start    = Int(default=0, help="min value which can be input")
    step     = Int(default=1,  help="step value which can be input")
    end      = Int(default=10, help="max value which can be input")

class DpxFloatInput(InputWidget):
    """ Single-line input widget. """
    __implementation__ = "intinput.coffee"

    value    = Float(default=0.,  help="Initial or entered int value")
    start    = Float(default=0.,  help="min value which can be input")
    step     = Float(default=1.,  help="step value which can be input")
    end      = Float(default=10., help="max value which can be input")

class DpxTextInput(InputWidget):
    """ Single-line input widget. """
    __implementation__ = "intinput.coffee"

    value       = String(default="", help="Initial or entered int value")
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

class BeadView(BokehView):
    "Widget for controlling the current beads"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._inp   = None

    def getroots(self, doc):
        raise NotImplementedError()

    @property
    def input(self):
        "returns the bokeh model"
        return self._inp

    @property
    def _root(self):
        return self._ctrl.getGlobal("project").track.get()

    @property
    def _bead(self):
        return self._ctrl.getGlobal("project").bead.get()

    @_bead.setter
    def _bead(self, val):
        return self._ctrl.getGlobal("project").bead.set(val)

    def _isdiscardedbeads(self, parent, task):
        return isinstance(task, DiscardedBeadsTask) and parent is self._root

class BeadInput(BeadView):
    "Spinner for controlling the current bead"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        css = self._ctrl.getGlobal('css').beadinput
        css.defaults = {'title': 'Bead', 'width': 60, 'height' : 25}

        cnf = self._ctrl.getGlobal('config')
        cnf.keypress.defaults = {'beadup'   : 'PageUp',
                                 'beaddown' : 'PageDown'}

        self.__beads = np.empty((0,), dtype = 'i4')

    def getroots(self, _):
        "adds items to doc"
        css       = self._ctrl.getGlobal('css').beadinput
        self._inp = DpxIntInput(disabled = True,
                                **css.getitems('height', 'width', 'title'))
        self._inp.on_change("value", self.__onchange_cb)

        self._ctrl.getGlobal('project').observe('track', 'bead', self.__onproject)
        self._ctrl.observe("updatetask", "addtask", "removetask", self.__onupdatetask)

        self._keys.addKeyPress(('keypress.beadup',
                                lambda: self.__onchange_cb('', '', self._inp.value+1)))
        self._keys.addKeyPress(('keypress.beaddown',
                                lambda: self.__onchange_cb('', '', self._inp.value-1)))
        return self._inp


    def __setbeads(self):
        "returns the active beads"
        root  = self._root
        track = self._ctrl.track(root)
        if track is None:
            return []

        task  = self._ctrl.task(root, DiscardedBeadsTask)
        beads = set(track.beadsonly.keys()) - set(getattr(task, 'beads', []))

        self.__beads = np.sort(tuple(beads)) if len(beads) else np.empty((0,), dtype = 'i4')

        upd = {'disabled': len(self.__beads) == 0, 'value': self._bead}
        if len(self.__beads):
            upd['start'] = self.__beads[0]
            upd['end']   = self.__beads[-1]

        self._inp.update(**upd)

    def __setvalue(self, bead):
        if self._inp.disabled:
            return

        if bead is None:
            bead = self.__beads[0]
        elif bead not in self.__beads:
            bead = self.__beads[min(len(self.__beads)-1,
                                    np.searchsorted(self.__beads, bead))]

        if bead == self._bead:
            self._inp.value = bead
        else:
            with self.action:
                self._bead = bead

    def __onchange_cb(self, attr, old, new):
        self.__setvalue(new)

    def __onproject(self, items):
        if 'track' in items:
            self.__setbeads()
        self.__setvalue(self._bead)

    def __onupdatetask(self, parent = None, task = None, **_):
        if self._isdiscardedbeads(parent, task):
            self.__setbeads()
            self.__setvalue(self._bead)

class  RejectedBeadsInput(BeadView):
    "Toolbar with a bead spinner"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        css = self._ctrl.getGlobal('css').rejectedbeads
        css.defaults = {'title': "Discarded", 'width': 80, 'height' : 25}

    def getroots(self, doc):
        "Adds keypress for changin beads"
        css = self._ctrl.getGlobal("css")
        self._inp = DpxTextInput(**css.rejectedbeads.getitems('title', 'width', 'height'))
        self._inp.on_change('value', self.__ondiscarded_cb)
        self._ctrl.observe("updatetask", "addtask", self.__onupdatetask)
        self._ctrl.observe("removetask",            self.__onremovetask)
        self._ctrl.getGlobal('project').track.observe(self.__onproject)
        return self._inp

    def __ondiscarded_cb(self, attr, old, new):
        vals = set()
        for i in re.split('[:;,]', new):
            try:
                vals.add(int(i))
            except ValueError:
                continue

        root = self._root
        task = self._ctrl.task(root, DiscardedBeadsTask)
        if vals == set(getattr(task, 'beads', [])):
            return

        with self.action:
            if task is None:
                self._ctrl.addTask(root, DiscardedBeadsTask(beads = list(vals)), index = 1)
            elif len(vals) == 0:
                self._ctrl.removeTask(root, task)
            else:
                self._ctrl.updateTask(root, task, beads = list(vals))

    def __onupdatetask(self, parent = None, task = None, **_):
        if self._isdiscardedbeads(parent, task):
            self._inp.value = ', '.join(str(i) for i in sorted(task.beads))

    def __onremovetask(self, parent = None, task = None, **_):
        if self._isdiscardedbeads(parent, task):
            self._inp.value = ''

    def __onproject(self):
        root  = self._root
        beads = getattr(self._ctrl.task(root, DiscardedBeadsTask), 'beads', [])
        self._inp.value = ', '.join(str(i) for i in sorted(beads))
