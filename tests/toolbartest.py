#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests legacy data """
import  flexx.app       as flexxapp

import  app.default     as defaultapp   # pylint: disable=no-member,import-error
from    view.toolbar    import ToolBar  # pylint: disable=no-member,import-error
import  view.dialog
from    testdata        import path

class PressEvent:
    u"Simulated key press"
    def __init__(self, val):
        if '-' in val:
            self.modifiers = val.split('-')[:-1]
            self.key       = val.split('-')[-1]
        else:
            self.modifiers = []
            self.key       = val

    def __call__(self, mdl):
        return mdl._View__onKeyPress(self) # pylint: disable=protected-access

def press(key, mdl):
    u"simulate key press"
    return PressEvent(key)(mdl)

def test_menubar(monkeypatch):
    u"tests that the menubar works"
    def _tkopen(*_1, **_2):
        return path("small_legacy")

    monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)

    elem = defaultapp.launch(ToolBar) # pylint: disable=no-member

    asserts = []
    def _actions():
        ctrl = elem._ctrl   # pylint: disable=protected-access
        box  = elem._box    # pylint: disable=protected-access
        def _checknone():
            asserts.append(len(box.children) == 3)
            asserts.append(ctrl.getGlobal('current.track', default = None) is None)
            asserts.append(ctrl.getGlobal('current.task',  default = None) is None)

        def _checkopen():
            track = ctrl.getGlobal('current.track')
            asserts.append(len(box.children) == 4)
            asserts.append(track.path == path('small_legacy'))
            asserts.append(track      is ctrl.getGlobal('current.task'))

        try:
            _checknone()

            press('Ctrl-o', elem)
            _checkopen()

            press('Ctrl-z', elem)
            _checknone()

            press('Ctrl-y', elem)
            _checkopen()
        except:             # pylint: disable=bare-except
            asserts.append(False)
        finally:
            press('Ctrl-q', elem)

    flexxapp.call_later(1, _actions)
    flexxapp.start()
    assert len(asserts) == 12
    for i, val in enumerate(asserts):
        assert val, str(i)
