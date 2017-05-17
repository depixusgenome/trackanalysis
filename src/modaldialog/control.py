#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows creating modals from anywhere with updates fenced by an Action
"""
from control.action import Action
from .modal         import DpxModal

class ControlledDpxModal(DpxModal):
    "DpxModal with controller"
    def __init__(self, ctrl, **kwa):
        super().__init__(**kwa)
        self._ctrl = ctrl

    def _setvalues(self, converters, itms):
        with Action(self):
            super()._setvalues(converters, itms)
