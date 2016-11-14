#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for testing views"
import traceback
import flexx.app as flexxapp
import pytest

class PyPressEvent:
    u"Simulated key press"
    def __init__(self, val):
        if '-' in val:
            self.modifiers = val.split('-')[:-1]
            self.key       = val.split('-')[-1]
        else:
            self.modifiers = []
            self.key       = val

    def __call__(self, mdl):
        # pylint: disable=protected-access
        if isinstance(mdl, FlexxAction):
            return mdl.view._keys.onKeyPress(self)
        else:
            return mdl._keys.onKeyPress(self)

def pypress(key, mdl = None):
    u"simulate key press"
    if mdl is None:
        return PyPressEvent(key)
    else:
        return PyPressEvent(key)(mdl)

class FlexxAction:
    u"All things to make gui testing easy"
    def __init__(self, mkpatch):
        self.monkeypatch = mkpatch
        self.view        = None
        self.ind         = 0
        self.exc         = None
        self.info        = []

    def __getattr__(self, name):
        return getattr(self.view, '_'+name)

    def setattr(self, *args, **kwargs):
        u"apply monkey patch"
        self.monkeypatch.setattr(*args, **kwargs)
        return self

    def init(self, launch, item):
        u"creates and returns the model"
        launcher  = __import__("app."+launch, fromlist = ['launch'])
        self.view = launcher.launch(item)
        return self

    def pypress(self, key, now = False):
        u"press one key in python server"
        return pypress(key, self) if now else pypress(key)

    def quit(self, now = True):
        u"stops server"
        self.pypress('Ctrl-q', now)
        return self

    def asserts(self, val, msg = None):
        u"accumulates assertions: pytest doesn't work otherwise"
        self.info.append((val, msg))

    def run(self, *actions, path = None, count = None):
        u"Runs a series of actions"
        def _run():
            self.ind += 1
            try:
                actions[self.ind-1](self)
            except Exception as exc:             # pylint: disable=broad-except
                self.exc = exc
                traceback.print_exc()
                self.quit()
            else:
                if self.ind >= len(actions):
                    self.quit()
                else:
                    flexxapp.call_later(1, _run)

        if path is not None:
            import view.dialog                  # pylint: disable=import-error
            def _tkopen(*_1, **_2):
                from testdata import path as _path
                return _path(path)
            self.monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)

        flexxapp.call_later(1, _run)
        flexxapp.start()
        if count is not None:
            self.test(count)
        return self

    def test(self, cnt):
        u"checks wether all info is True"
        assert self.exc is None
        if cnt:
            assert len(self.info) == cnt
            for i, (val, msg) in enumerate(self.info):
                assert val is True, str(i) if msg is None else str(i)+': '+str(msg)

@pytest.fixture()
def flexxaction(monkeypatch):
    u"""
    Create a flexxaction fixture.
    Use case is:

    > def test_myview(flexxaction):
    >    flexxaction.init('module containing launch', MyViewClass)
    >    flexxaction.run(lambda flexxact: flexxact.pypress('Ctrl-o'),
    >                    lambda flexxact: check(flexxact.view, flexxact.ctrl),
    >                    ...)


    flexxaction.run takes a list of functions which can call on the view or
    check its state.

    flexxaction.view is the created view. Any of its protected attribute can
    be accessed directly, for example flexxaction.view._ctrl  can be accessed
    through flexxaction.ctrl.
    """
    return FlexxAction(monkeypatch)
