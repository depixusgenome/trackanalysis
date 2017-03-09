#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for testing views"
from typing                import Optional  # pylint: disable=unused-import
import sys
import tempfile

import pytest

from tornado.ioloop        import IOLoop
from bokeh.core.properties import Int, String, Dict, Any, Instance
from bokeh.model           import Model
from bokeh.document        import Document  # pylint: disable=unused-import
from bokeh.server.server   import Server    # pylint: disable=unused-import

from view.keypress         import KeyPressManager

class DpxTestLoaded(Model):
    """
    This starts tests once flexx/browser window has finished loading
    """
    __implementation__ = """
        import *        as _    from "underscore"
        import *        as $    from "jquery"
        import *        as p    from "core/properties"
        import {Model}          from "model"

        export class DpxTestLoadedView

        export class DpxTestLoaded extends Model
            default_view: DpxTestLoadedView
            type: "DpxTestLoaded"
            constructor : (attributes, options) ->
                super(attributes, options)
                @listenTo(@, 'change:event', @_press)
                $((e) => @done = 1)

            _create_evt: (name) ->
                evt = $.Event(name)
                evt.altKey   = @event.alt
                evt.shiftKey = @event.shift
                evt.ctrlKey  = @event.ctrl
                evt.metaKey  = @event.meta
                evt.key      = @event.key

                return evt

            _press: () ->
                if @model?
                    @model.dokeydown?(@_create_evt('keydown'))
                    @model.dokeyup?(@_create_evt('keyup'))

            @define {
                done:  [p.Number, 0]
                event: [p.Any,   {}]
                model: [p.Any,   {}]
            }
                         """
    done  = Int(0)
    event = Dict(String, Any)
    model = Instance(Model)
    def press(self, key, model):
        u"Sets-up a new keyevent in JS"
        val = '-' if key == '-' else key.split('-')[-1]
        evt = dict(alt   = 'Alt-'     in key,
                   shift = 'Shift-'   in key,
                   ctrl  = 'Control-' in key,
                   meta  = 'Meta-'    in key,
                   key   = val)
        self.model = model
        self.event = evt

class _ManagedServerLoop:
    u"""
    lets us use a current IOLoop with "with"
    and ensures the server unlistens
    """
    loop = property(lambda self: self.server.io_loop)
    ctrl = property(lambda self: getattr(self.view, '_ctrl'))

    @property
    def loading(self) -> 'Optional[DpxTestLoaded]':
        u"returns the model which allows tests to javascript"
        return next(iter(getattr(self.doc, 'roots', [])), None)

    class _Dummy:
        @staticmethod
        def setattr(*args):
            u"dummy"
            return setattr(*args)

    def __init__(self, mkpatch, kwa:dict) -> None:
        self.monkeypatch = self._Dummy() if mkpatch is None else mkpatch # type: ignore
        self.server  = None # type: Server
        self.view    = None # type: ignore
        self.doc     = None # type: Document
        self.kwa     = kwa

    def __exit__(self, *_):
        if self.server is not None:
            self.quit()

    def __buildserver(self, kwa):
        kwa['io_loop'] = IOLoop()
        kwa['io_loop'].make_current()

        app, mod, fcn = self.kwa.pop('_args_')
        if '.' in mod and 'A' <= mod[mod.rfind('.')+1] <= 'Z':
            lmod  = mod[:mod.rfind('.')]
            lattr = mod[mod.rfind('.')+1:]
            launchmod = getattr(__import__(lmod, fromlist = (lattr,)), lattr)
            launch    = getattr(launchmod, fcn)
        else:
            launch    = getattr(getattr(__import__(mod), mod), fcn)
        server        = launch(app, server = kwa)

        @classmethod
        def _open(_, doc, _func_ = server.MainView.open):
            self.doc = doc
            doc.add_root(DpxTestLoaded())
            self.view = _func_(doc)
            return self.view
        server.MainView.open = _open

        def _close(this, _func_ = server.MainView.close):
            self.server = None
            ret = _func_(this)
            return ret

        server.MainView.close = _close
        return server

    def __enter__(self):
        self.server = self.__buildserver(self.kwa)

        def _start():
            u"Waiting for the document to load"
            if getattr(self.loading, 'done', False):
                self.loop.stop()
            else:
                self.loop.call_later(0.5, _start)
        _start()

        self.server.start()
        self.loop.start()
        return self

    @staticmethod
    def path(path:str) -> str:
        u"returns the path to testing data"
        from testingcore import path as _testpath
        return _testpath(path)

    def cmd(self, fcn, *args, andstop = True, **kwargs):
        u"send command to the view"
        if andstop:
            def _cmd():
                fcn(*args, **kwargs)
                self.loop.call_later(.5, self.loop.stop)
        else:
            _cmd = fcn
        self.doc.add_next_tick_callback(_cmd)
        self.loop.start()

    def quit(self):
        u"close the view"
        def _quit():
            self.server.unlisten()
            self.ctrl.close()

        self.cmd(_quit, andstop = False)

    def load(self, path:str):
        u"loads a path"
        import view.dialog  # pylint: disable=import-error
        def _tkopen(*_1, **_2):
            return self.path(path)
        self.monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)
        self.press('Control-o')

    def get(self, clsname, attr):
        u"Returns a private attribute in the view"
        key = '_'+clsname+'__'+attr
        if key in self.view.__dict__:
            return self.view.__dict__[key]

        key = '_'+attr
        if key in self.view.__dict__:
            return self.view.__dict__[key]

        return self.view.__dict__[attr]

    def press(self, key:str, src = None):
        u"press one key in python server"
        if src is None:
            for root in self.doc.roots:
                if isinstance(root, KeyPressManager):
                    self.cmd(self.loading.press, key, root)
                    break
            else:
                raise KeyError("Missing KeyPressManager in doc.roots")
        else:
            self.cmd(self.loading.press, key, src)

class BokehAction:
    u"All things to make gui testing easy"
    def __init__(self, mkpatch):
        self.monkeypatch = mkpatch
        class _Dummy:
            user_config_dir = lambda *_: tempfile.mktemp()
        sys.modules['appdirs'] = _Dummy

    def serve(self, app:type, mod:str  = 'default', **kwa) -> _ManagedServerLoop:
        u"Returns a server managing context"
        kwa['_args_'] = app, mod, 'serve'
        return _ManagedServerLoop(self.monkeypatch, kwa)

    def launch(self, app:type, mod:str  = 'default', **kwa) -> _ManagedServerLoop:
        u"Returns a server managing context"
        kwa['_args_'] = app, mod, 'launch'
        return _ManagedServerLoop(self.monkeypatch, kwa)

    def setattr(self, *args, **kwargs):
        u"apply monkey patch"
        self.monkeypatch.setattr(*args, **kwargs)
        return self

@pytest.fixture()
def bokehaction(monkeypatch):
    u"""
    Create a BokehAction fixture.
    Use case is:

    > def test_myview(bokehaction):
    >    with bokehaction.server(ToolBar, 'default') as server:
    >       server.load('small_legacy')
    >       assert ...
    >       server.press('Control-z')

    BokehAction.view is the created view. Any of its protected attribute can
    be accessed directly, for example BokehAction.view._ctrl  can be accessed
    through BokehAction.ctrl.
    """
    if monkeypatch is None:
        from _pytest.monkeypatch import MonkeyPatch
        import warnings
        warnings.warn("Unsafe call to MonkeyPatch. Use only for manual debugging")
        monkeypatch = MonkeyPatch()
    return BokehAction(monkeypatch)
