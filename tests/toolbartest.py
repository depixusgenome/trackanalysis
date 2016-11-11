#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u""" Tests legacy data """
import os
import flexx.app       as flexxapp

import app.default     as defaultapp   # pylint: disable=no-member,import-error
from   view.toolbar    import ToolBar  # pylint: disable=no-member,import-error
import view.dialog
from   testdata        import path

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
        return mdl._keys.onKeyPress(self)       # pylint: disable=protected-access

def press(key, mdl):
    u"simulate key press"
    return PressEvent(key)(mdl)

def test_menubar(monkeypatch):
    u"tests that the menubar works"
    def _tkopen(*_1, **_2):
        return path("small_legacy")

    monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)

    elem = defaultapp.launch(ToolBar)           # pylint: disable=no-member

    asserts = []
    def _actions(start = 0, tries = 0):
        ctrl = elem._ctrl                       # pylint: disable=protected-access
        curr = ctrl.getGlobal('current')
        box  = elem._box                        # pylint: disable=protected-access
        def _checknone():
            asserts.append(len(box.children) == 3)
            asserts.append(curr.get('track', default = None) is None)
            asserts.append(curr.get('task',  default = None) is None)

        def _checkopen():
            track = curr.get('track')
            pth1  = os.path.abspath(track.path)
            pth2  = os.path.abspath(path('small_legacy'))
            asserts.append(len(box.children) == 4)
            asserts.append(pth1  == pth2)
            asserts.append(track is curr.get('task'))
            asserts.append(ctrl.getGlobal('config', 'last.path.trk') == pth1)

        print("Step %d, try %d" % (start, tries))
        def _retry(cnt):
            if len(box.children) == cnt:
                if tries == 10:
                    raise IndexError("Tried too long step %d" % start)
                flexxapp.call_later(1, lambda: _actions(start, tries+1))
                return True
            return False

        try:
            if start == 0:
                _checknone()
                press('Ctrl-o', elem)
            elif start == 1:
                if _retry(3):
                    return
                _checkopen()
                press('Ctrl-z', elem)
            elif start == 2:
                if _retry(4):
                    return
                _checknone()
                press('Ctrl-y', elem)
            elif start == 3:
                if _retry(3):
                    return
                _checkopen()
        except:             # pylint: disable=bare-except
            asserts.append(False)
            press('Ctrl-q', elem)
        else:
            if start < 3:
                flexxapp.call_later(1, lambda: _actions(start+1))
            else:
                press('Ctrl-q', elem)

    flexxapp.call_later(1, _actions)
    flexxapp.start()
    assert len(asserts) == 14
    for i, val in enumerate(asserts):
        assert val, str(i)
