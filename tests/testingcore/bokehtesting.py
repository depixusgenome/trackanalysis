#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Utils for testing views"
from   typing    import Optional, Union, Sequence, Any
import sys
import tempfile
import warnings
import inspect

warnings.filterwarnings('ignore',
                        category = DeprecationWarning,
                        message  = '.*elementwise == comparison failed.*')
warnings.filterwarnings('ignore',
                        category = DeprecationWarning,
                        message  = '.* deprecated in Bokeh 0.12.6 .*')

with warnings.catch_warnings():
    warnings.filterwarnings('ignore', category = DeprecationWarning)
    import pytest
    from bokeh.model           import Model
    from bokeh.document        import Document
    from bokeh.server.server   import Server
    import bokeh.core.properties as     props

# pylint: disable=wrong-import-position
from tornado.ioloop        import IOLoop
from view.keypress         import KeyPressManager
from utils.logconfig       import getLogger

LOGS = getLogger()

class DpxTestLoaded(Model):
    """
    This starts tests once flexx/browser window has finished loading
    """
    __implementation__ = """
        import *        as $    from "jquery"
        import *        as p    from "core/properties"
        import {Model}          from "model"
        import {DOMView}        from "core/dom_view"

        export class DpxTestLoadedView extends DOMView
            className: "dpx-test"
            initialize: (options) ->
                super(options)
                @connect(@model.properties.event_cnt.change, () => @model._press())
                @connect(@model.properties.value_cnt.change, () => @model._change())

        export class DpxTestLoaded extends Model
            default_view: DpxTestLoadedView
            type: "DpxTestLoaded"
            constructor : (attributes, options) ->
                super(attributes, options)
                $((e) => @done = 1)

                self = @

                oldlog       = console.log
                console.log  = () -> self._tostr(oldlog, 'debug', arguments)

                oldinfo      = console.info
                console.info = () -> self._tostr(oldinfo, 'info', arguments)

                oldwarn      = console.warn
                console.warn = () -> self._tostr(oldwarn, 'warn', arguments)

            _tostr: (old, name, args) ->
                str = ""
                for i in args
                    str = str + " " + i
                @[name] = ""
                @[name] = str

                old.apply(console, args)

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

            _change: () ->
                if @model?
                    mdl = @model
                    for i in @attrs
                        mdl = mdl[i]

                    mdl[@attr] = @value
                    if @attrs.length == 0
                        @model.properties[@attr].change.emit()
                    else
                        @model.properties[@attrs[0]].change.emit()

            @define {
                done:  [p.Number, 0]
                event: [p.Any,   {}]
                event_cnt: [p.Int, 0]
                model: [p.Any,   {}]
                attrs: [p.Array, []]
                attr : [p.String, '']
                value: [p.Any,   {}]
                value_cnt: [p.Int, 0]
                debug: [p.String, '']
                warn: [p.String, '']
                info: [p.String, '']
            }
                         """
    done        = props.Int(0)
    event       = props.Dict(props.String, props.Any)
    event_cnt   = props.Int(0)
    model       = props.Instance(Model)
    attrs       = props.List(props.String, default = [])
    attr        = props.String()
    value       = props.Any()
    value_cnt   = props.Int(0)
    debug       = props.String()
    warn        = props.String()
    info        = props.String()
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.on_change("debug", self.__log_cb)
        self.on_change("warn",  self.__log_cb)
        self.on_change("info",  self.__log_cb)

    @staticmethod
    def __log_cb(attr, old, new):
        if new != '':
            getattr(LOGS, attr)('JS <- '+new)

    def press(self, key, model):
        "Sets-up a new keyevent in JS"
        val = '-' if key == '-' else key.split('-')[-1]
        evt = dict(alt   = 'Alt-'     in key,
                   shift = 'Shift-'   in key,
                   ctrl  = 'Control-' in key,
                   meta  = 'Meta-'    in key,
                   key   = val)
        self.model = model
        self.event = evt
        self.event_cnt += 1

    def change(self, model:Model, attrs: Union[str, Sequence[str]], value: Any):
        "Changes a model attribute on the browser side"
        self.model = model
        self.attrs = list(attrs)[:-1] if isinstance(attrs, (tuple, list)) else []
        self.attr  = attrs[-1]        if isinstance(attrs, (tuple, list)) else attrs
        self.value = value
        self.value_cnt += 1

class WidgetAccess:
    "Access to bokeh models"
    _none = type('_none', (), {})
    def __init__(self, docs, key = None):
        self._docs = docs if isinstance(docs, (list, tuple)) else (docs,)
        self._key  = key

    def __getitem__(self, value):
        if isinstance(value, type):
            if self._key is not None:
                val = next((i for doc in self._docs for i in doc.select({'type': value})),
                           self._none)
                if val is not self._none:
                    return val
            return next(i for doc in self._docs for i in doc.select({'type': value}))
        else:
            itms = tuple()
            for doc in self._docs:
                itms += tuple(doc.select({'name': value}))
            if len(itms) > 0:
                return WidgetAccess(itms)
            key = value if self._key is None else self._key + '.' + value
            return WidgetAccess(tuple(self._docs), key)

    def __getattr__(self, key):
        return super().__getattribute__(key) if key[0] == '_' else getattr(self(), key)

    def __setattr__(self, key, value):
        return super().__setattr__(key, value) if key[0] == '_' else setattr(self(), key, value)

    def __call__(self):
        if self._key is not None:
            raise KeyError("Could not find "+ self._key)
        else:
            return self._docs[0]

class _ManagedServerLoop:
    """
    lets us use a current IOLoop with "with"
    and ensures the server unlistens
    """
    loop     = property(lambda self: self.server.io_loop)
    ctrl     = property(lambda self: getattr(self.view, '_ctrl'))
    roottask = property(lambda self: self.ctrl.getGlobal('project').track.get())
    track    = property(lambda self: self.ctrl.track(self.roottask))
    def task(self, task):
        "returns a task"
        return self.ctrl.task(self.roottask, task)

    @property
    def loading(self) -> Optional[DpxTestLoaded]:
        "returns the model which allows tests to javascript"
        return next(iter(getattr(self.doc, 'roots', [])), None)

    class _Dummy:
        @staticmethod
        def setattr(*args):
            "dummy"
            return setattr(*args)

    def __init__(self, mkpatch, kwa:dict) -> None:
        self.monkeypatch      = self._Dummy() if mkpatch is None else mkpatch # type: ignore
        self.server: Server   = None
        self.view:   Any      = None
        self.doc:    Document = None
        self.kwa              = kwa
        self.__warnings: Any  = None

    @staticmethod
    def __import(amod):
        if not isinstance(amod, str):
            return amod

        if '.' in amod and 'A' <= amod[amod.rfind('.')+1] <= 'Z':
            modname = amod[:amod.rfind('.')]
            attr    = (amod[amod.rfind('.')+1:],)
        else:
            modname = amod
            attr    = tuple()

        mod = __import__(modname)
        for i in tuple(modname.split('.')[1:]) + attr:
            mod = getattr(mod, i)
        return mod

    def __patchserver(self, server):
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

    def __getlauncher(self):
        tmpapp, mod, fcn = self.kwa.pop('_args_')
        app              = self.__import(tmpapp)
        if not isinstance(app, type):
            from view.base import BokehView
            pred = lambda i: (isinstance(i, type)
                              and i.__module__ == app.__name__
                              and issubclass(i, BokehView))
            pot  = tuple(i for _, i in inspect.getmembers(app, pred))
            assert len(pot) == 1
            app  = pot[0]

        return app, getattr(self.__import(mod), fcn)

    def __buildserver(self, kwa):
        kwa['io_loop'] = IOLoop()
        kwa['io_loop'].make_current()

        app, launch = self.__getlauncher()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', '.*inspect.getargspec().*')
            import app.launcher as _launcher
            old, _launcher.CAN_LOAD_JS = _launcher.CAN_LOAD_JS, False
            try:
                server = launch(app, server = kwa)
            finally:
                _launcher.CAN_LOAD_JS = old

        self.__patchserver(server)
        return server

    def __enter__(self):
        self.server     = self.__buildserver(self.kwa)
        self.__warnings = warnings.catch_warnings()
        self.__warnings.__enter__()
        warnings.filterwarnings('ignore', '.*inspect.getargspec().*')

        def _start():
            "Waiting for the document to load"
            if getattr(self.loading, 'done', False):
                self.loop.call_later(2., self.loop.stop)
            else:
                self.loop.call_later(0.5, _start)
        _start()

        self.server.start()
        self.loop.start()
        return self

    def __exit__(self, *_):
        if self.server is not None:
            self.quit()
        self.__warnings.__exit__(*_)

    @staticmethod
    def path(path:str) -> str:
        "returns the path to testing data"
        from testingcore import path as _testpath
        return _testpath(path)

    def cmd(self, fcn, *args, andstop = True, andwaiting = 2., **kwargs):
        "send command to the view"
        if andstop:
            def _cmd():
                fcn(*args, **kwargs)
                self.loop.call_later(andwaiting, self.loop.stop)
        else:
            _cmd = lambda: fcn(*args, **kwargs)
        self.doc.add_next_tick_callback(_cmd)
        if not self.loop._running: # pylint: disable=protected-access
            self.loop.start()

    def wait(self, time = 2.):
        "wait some more"
        self.cmd(lambda: None, andwaiting = time)

    def quit(self):
        "close the view"
        def _quit():
            self.server.unlisten()
            self.ctrl.close()

        self.cmd(_quit, andstop = False)

    def load(self, path:str, andpress = True, **kwa):
        "loads a path"
        import view.dialog  # pylint: disable=import-error
        def _tkopen(*_1, **_2):
            return self.path(path)
        self.monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)
        if andpress:
            self.press('Control-o', **kwa)

    def get(self, clsname, attr):
        "Returns a private attribute in the view"
        key = '_'+clsname+'__'+attr
        if key in self.view.__dict__:
            return self.view.__dict__[key]

        key = '_'+attr
        if key in self.view.__dict__:
            return self.view.__dict__[key]

        return self.view.__dict__[attr]

    def press(self, key:str, src = None, **kwa):
        "press one key in python server"
        if src is None:
            for root in self.doc.roots:
                if isinstance(root, KeyPressManager):
                    self.cmd(self.loading.press, key, root, **kwa)
                    break
            else:
                raise KeyError("Missing KeyPressManager in doc.roots")
        else:
            self.cmd(self.loading.press, key, src, **kwa)

    def click(self, model: Union[str,dict,Model], **kwa):
        "Clicks on a button on the browser side"
        if isinstance(model, str):
            mdl = next(iter(self.doc.select(dict(name = model))))
        elif isinstance(model, dict):
            mdl = next(iter(self.doc.select(model)))
        else:
            mdl = model
        self.change(mdl, 'click', mdl.click+1, **kwa)

    def change(self,        # pylint: disable=too-many-arguments
               model: Union[str,dict,Model],
               attrs: Union[str, Sequence[str]],
               value: Any,
               browser     = True,
               withpath    = None,
               withnewpath = None):
        "Changes a model attribute on the browser side"
        if withnewpath is not None:
            import view.dialog  # pylint: disable=import-error
            def _tkopen1(*_1, **_2):
                return withnewpath
            self.monkeypatch.setattr(view.dialog, '_tkopen', _tkopen1)

        elif withpath is not None:
            import view.dialog  # pylint: disable=import-error
            def _tkopen(*_1, **_2):
                return self.path(withpath)
            self.monkeypatch.setattr(view.dialog, '_tkopen', _tkopen)

        if isinstance(model, str):
            mdl = next(iter(self.doc.select(dict(name = model))))
        elif isinstance(model, dict):
            mdl = next(iter(self.doc.select(model)))
        else:
            mdl = model
        if browser:
            self.cmd(self.loading.change, mdl, attrs, value)
        else:
            assert isinstance(attrs, str)
            def _cb():
                setattr(mdl, attrs, value)
            self.cmd(_cb)

    @property
    def widget(self):
        "Returns something to access web elements"
        return WidgetAccess(self.doc)

class BokehAction:
    "All things to make gui testing easy"
    def __init__(self, mkpatch):
        self.monkeypatch = mkpatch
        tmp = tempfile.mktemp()+"_test"
        class _Dummy:
            user_config_dir = lambda *_: tmp+"/"+_[-1]
        sys.modules['appdirs'] = _Dummy

    def serve(self, app:Union[type, str], mod:str  = 'default', **kwa) -> _ManagedServerLoop:
        "Returns a server managing context"
        kwa['_args_'] = app, mod, 'serve'
        return _ManagedServerLoop(self.monkeypatch, kwa)

    def launch(self, app:Union[type, str], mod:str  = 'default', **kwa) -> _ManagedServerLoop:
        "Returns a server managing context"
        kwa['_args_'] = app, mod, 'launch'
        return _ManagedServerLoop(self.monkeypatch, kwa)

    def setattr(self, *args, **kwargs):
        "apply monkey patch"
        self.monkeypatch.setattr(*args, **kwargs)
        return self

@pytest.fixture()
def bokehaction(monkeypatch):
    """
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
        warnings.warn("Unsafe call to MonkeyPatch. Use only for manual debugging")
        monkeypatch = MonkeyPatch()
    return BokehAction(monkeypatch)
