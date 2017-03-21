#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"basic view module"
from typing               import Callable
from bokeh.models.widgets import Button
from bokeh.layouts        import layout

from control        import Controller                   # pylint: disable=unused-import
from control.action import ActionDescriptor, Action     # pylint: disable=unused-import
from .keypress      import KeyPressManager              # pylint: disable=unused-import

class View:
    "Classes to be passed a controller"
    action = ActionDescriptor()
    ISAPP  = False
    def __init__(self, **kwargs):
        "initializes the gui"
        self._ctrl  = kwargs['ctrl']  # type: Controller

    def startup(self, path, script):
        "runs a script or opens a file on startup"
        with self.action:
            if path is not None:
                self._ctrl.openTrack(path)
            if script is not None:
                script(self, self._ctrl)

    def observe(self):
        "whatever needs to be initialized"

    def ismain(self):
        "Allows setting-up stuff only when the view is the main one"

    def close(self):
        "closes the application"
        self._ctrl.close()
        self._ctrl = None

def enableOnTrack(ctrl, *itms):
    "Enables/disables view elements depending on the track status"
    for ite in itms:
        ite.disabled = True

    def _oncurrent(items):
        if 'track' in items:
            val = items['track'].value is items.empty
            for ite in itms:
                ite.disabled = val
    getattr(ctrl, '_ctrl', ctrl).observe("globals.current", _oncurrent)

class BokehView(View):
    "A view with a gui"
    def __init__(self, **kwargs):
        "initializes the gui"
        super().__init__(**kwargs)
        self._keys = kwargs['keys']  # type: KeyPressManager

    def close(self):
        "closes the application"
        super().close()
        self._keys.close()
        self._keys = None

    @classmethod
    def open(cls, doc, **kwa):
        "starts the application"
        self = cls(**kwa)
        self.addtodoc(doc)
        return self

    def enableOnTrack(self, *itms):
        "Enables/disables view elements depending on the track status"
        enableOnTrack(self._ctrl, *itms)

    def addtodoc(self, doc):
        "Adds one's self to doc"
        self._keys.getroots(doc)
        roots = self.getroots(doc)
        if len(roots) == 1:
            doc.add_root(roots[0])
        else:
            doc.add_root(layout(roots, sizing_mode = 'stretch_both'))

    def getroots(self, doc):
        "returns object root"
        raise NotImplementedError("Add items to doc")

    def button(self, fcn:Callable, title:str, prefix = 'keypress', **kwa):
        "creates and connects a button"
        kwa.setdefault('label',  title.capitalize())
        kwa.setdefault('width',  self._ctrl.getGlobal('css', 'button.width'))
        kwa.setdefault('height', self._ctrl.getGlobal('css', 'button.height'))

        btn = Button(**kwa)
        btn.on_click(fcn)
        self._keys.addKeyPress((prefix+'.'+title.lower(), fcn))
        return btn
