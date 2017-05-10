#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"basic view module"
from typing               import Callable
from concurrent.futures   import ThreadPoolExecutor

from bokeh.document       import Document         # pylint: disable=unused-import
from bokeh.models.widgets import Button
from bokeh.themes         import Theme
from bokeh.layouts        import layout

from tornado.ioloop             import IOLoop
from tornado.platform.asyncio   import to_tornado_future

from control        import Controller             # pylint: disable=unused-import
from control.action import ActionDescriptor, Computation, Action
from .keypress      import KeyPressManager        # pylint: disable=unused-import


class View:
    "Classes to be passed a controller"
    action      = ActionDescriptor(Action)
    computation = ActionDescriptor(Computation)
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

def enableOnTrack(ctrl, *aitms):
    "Enables/disables view elements depending on the track status"
    litms = []
    def _get(obj):
        if isinstance(obj, (tuple, list)):
            for i in obj:
                _get(i)
        elif isinstance(obj, dict):
            for i in obj.values():
                _get(i)
        else:
            litms.append(obj)
    _get(aitms)
    itms = tuple(litms)
    for ite in itms:
        ite.disabled = True

    def _onproject(items, __lst__ = itms):
        if 'track' in items:
            val = items['track'].value is items.empty
            for ite in __lst__:
                ite.disabled = val
    getattr(ctrl, '_ctrl', ctrl).getGlobal("project").observe(_onproject)

POOL = ThreadPoolExecutor(1)
async def threadmethod(fcn, *args, pool = None, **kwa):
    "threads a method"
    if pool is None:
        pool = POOL
    return await to_tornado_future(pool.submit(fcn, *args, **kwa))

def spawn(fcn, *args, loop = None, **kwa):
    "spawns method"
    if loop is None:
        loop = IOLoop.current()
    loop.spawn_callback(fcn, *args, **kwa)

class BokehView(View):
    "A view with a gui"
    def __init__(self, **kwargs):
        "initializes the gui"
        super().__init__(**kwargs)
        css = self._ctrl.getGlobal('css')
        css.button.defaults = {'width': 90, 'height': 20}
        css.input .defaults = {'width': 90, 'height': 20}
        css.defaults = {'responsive': True, 'sizing_mode': 'scale_width'}
        dark = { 'attrs': { 'Figure': { 'background_fill_color': '#2F2F2F',
                                        'border_fill_color': '#2F2F2F',
                                        'outline_line_color': '#444444' },
                            'Axis':   { 'axis_line_color': "white",
                                        'axis_label_text_color': "white",
                                        'major_label_text_color': "white",
                                        'major_tick_line_color': "white",
                                        'minor_tick_line_color': "white"
                                      },
                            'Title':  { 'text_color': "white" } } }

        css.theme.dark.default  = dark
        css.theme.basic.default = {}
        css.theme.default       = 'dark'

        self._keys = kwargs['keys']  # type: KeyPressManager
        self._doc  = None            # type: Optional[Document]

    def close(self):
        "closes the application"
        super().close()
        self._doc  = None
        self._keys.close()
        self._keys = None

    @classmethod
    def open(cls, doc, **kwa):
        "starts the application"
        self = cls(**kwa)
        self.addtodoc(doc)
        self._ctrl.handle('applicationstarted') # pylint: disable=protected-access
        return self

    def enableOnTrack(self, *itms):
        "Enables/disables view elements depending on the track status"
        enableOnTrack(self._ctrl, *itms)

    def addtodoc(self, doc):
        "Adds one's self to doc"
        theme     = self._ctrl.getGlobal('css').theme.get(default = None)
        if isinstance(theme, str):
            theme = self._ctrl.getGlobal('css').theme[theme].get(default = None)
        doc.theme = Theme(json = theme)

        self._doc = doc
        self._keys.getroots(doc)
        roots = self.getroots(doc)
        if len(roots) == 1:
            doc.add_root(roots[0])
        elif self._ctrl.getGlobal('css').responsive.get():
            doc.add_root(layout(roots, responsive = True))
        else:
            mode = self._ctrl.getGlobal('css').sizing_mode.get()
            doc.add_root(layout(roots, sizing_mode = mode))

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
