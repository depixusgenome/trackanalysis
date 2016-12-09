#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Utils for testing views"
import pytest

from tornado.ioloop        import IOLoop
from bokeh.core.properties import Int, String, Dict, Any
from bokeh.model           import Model
from bokeh.document        import Document  # pylint: disable=unused-import
from bokeh.server.server   import Server    # pylint: disable=unused-import

from view.keypress         import KeyPressManager

class _OnLoadModel(Model):
    done  = Int(0)
    event = Dict(String, Any)

    __implementation__ = u"""
        p         = require "core/properties"
        Model     = require "model"
        $         = require "jquery"
        class DpxTestLoadedView

        class DpxTestLoaded extends Model
            default_view: DpxTestLoadedView
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
                evt.keyCode  = @event.keyCode
                evt.which    = @event.keyCode

                return evt

            _press: () ->
                @event.model.dokeydown?(@_create_evt('keydown'))
                @event.model.dokeyup?(@_create_evt('keyup'))

            @define {
                done:  [p.Number, 0]
                event: [p.Any, {}]
            }

        module.exports =
          View: DpxTestLoadedView
          Model: DpxTestLoaded
                          """

    def start(self, ioloop):
        u"Waiting for the document to load"
        if self.done:
            ioloop.stop()
        else:
            ioloop.call_later(0.5, self.start, ioloop)

    def press(self, key, model = ''):
        u"Sets-up a new keyevent in JS"
        val = '-' if key == '-' else key.split('-')[-1]
        evt = dict(model   = model,
                   alt     = 'Alt-'     in key,
                   shift   = 'Shift-'   in key,
                   ctrl    = 'Control-' in key,
                   meta    = 'Meta-'    in key,
                   key     = val,
                   keyCode = ord(val))
        self.event = evt

class _ManagedServerLoop:
    u"""
    lets us use a current IOLoop with "with"
    and ensures the server unlistens
    """
    loop = property(lambda self: self.server.io_loop)
    ctrl = property(lambda self: getattr(self.view, '_ctrl'))

    def __init__(self, mkpatch, application:type, module:str, kwa:dict) -> None:
        self.monkeypatch = mkpatch
        self.server  = None # type: Server
        self.view    = None # type: ignore
        self.loading = None # type: _OnLoadModel
        self.doc     = None # type: Document
        self.kwa     = kwa
        kwa['__app__'] = application
        kwa['__mod__'] = module

    def __exit__(self, *_):
        if self.server is not None:
            self.server.unlisten()
            self.server.stop()
            self.server.io_loop.close()

    def __buildserver(self, kwa):
        kwa['io_loop'] = IOLoop()
        kwa['io_loop'].make_current()

        mod     = self.kwa.pop('__mod__')
        launch  = getattr(__import__("app."+mod), mod).serve
        server  = launch(kwa.pop("__app__"), server = kwa)

        @classmethod
        def _open(_, doc, _func_ = server.MainView.open):
            self.doc = doc
            doc.add_root(self.loading)
            self.view = _func_(doc)
            return self.view
        server.MainView.open = _open

        def _close(this, _func_ = server.MainView.close):
            ret = _func_(this)
            self.server = None
            return ret

        server.MainView.close = _close
        return server

    def __enter__(self):
        self.server  = self.__buildserver(self.kwa)
        self.loading = _OnLoadModel()
        self.loading.start(self.loop)
        self.server.start()
        return self

    @staticmethod
    def path(path:str) -> str:
        u"returns the path to testing data"
        from testdata       import path as _testpath
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
        self.cmd(self.ctrl.close, andstop = False)

    def load(self, path:str):
        u"loads a path"
        import view.dialog  # pylint: disable=import-error
        def _tkopen(*_1, **_2):
            return self.path(path)
        self.monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)
        self.press('Control-o')

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

    def server(self, app:type, mod:str, **kwa) -> _ManagedServerLoop:
        u"Returns a server managing context"
        return _ManagedServerLoop(self.monkeypatch, app, mod, kwa)

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
    return BokehAction(monkeypatch)

#from pytest         import approx       # pylint: disable=no-name-in-module
#from flexxutils     import flexxaction  # pylint: disable=unused-import
#from view.trackplot import TrackPlot    # pylint: disable=no-member,import-error
#from view.toolbar   import ToolBar      # pylint: disable=no-member,import-error
#from testdata       import path
#
#def test_trackplot(flexxaction):        # pylint: disable=redefined-outer-name
#    u"test plot"
#    valx = []
#    valy = []
#    vals = []
#    def _printrng(**evts):
#        if 'x' in evts:
#            valx.append(evts['x'].value)
#        if 'y' in evts:
#            valy.append(evts['y'].value)
#        vals.append((valx[-1], valy[-1]))
#
#    def _get():
#        return self.children[0].node.children[0] # pylint: disable=undefined-variable
#
#    flexxaction.init('withtoolbar', TrackPlot, _get)
#    flexxaction.ctrl.observe("globals.current.plot.bead", _printrng)
#
#    flexxaction.run('Py-Control-o',        flexxaction.sleep(2),
#                    'Js- ',             'Js-Shift-ArrowUp',    'Js-Shift-ArrowRight',
#                    'Js-ArrowLeft',     'Js-ArrowUp',          'Js-ArrowRight',
#                    'Js-ArrowDown',     'Js-Shift-ArrowLeft',  'Js-Shift-ArrowDown',
#                    'Js-Shift-ArrowUp', 'Js-Shift-ArrowRight', 'Js- ',
#                    'Py-Control-z',        path = 'small_legacy')
#
#    truths = (((650.515,  1152.485),    (-0.0489966, 1.1207037013)),
#              ((650.515,  1152.485),    (0.18494344, 0.8867636370)),
#              ((750.909,  1052.091),    (0.18494344, 0.8867636370)),
#              ((690.6726, 991.8546),   (0.18494344, 0.8867636370)),
#              ((690.6726, 991.8546),   (0.32530748, 1.0271276756)),
#              ((750.909,  1052.091),    (0.32530748, 1.0271276756)),
#              ((750.909,  1052.091),    (0.18494344, 0.8867636370)),
#              ((650.515,  1152.485),    (0.18494344, 0.8867636370)),
#              ((650.515,  1152.485),    (-0.0489966, 1.1207037013)),
#              ((650.515,  1152.485),    (0.18494344, 0.8867636370)),
#              ((750.909,  1052.091),    (0.18494344, 0.8867636370)),
#              ((650.515,  1152.485),    (-0.0489966, 1.1207037013)))
#
#    assert len(truths) == len(vals)
#    assert vals == approx(truths)
