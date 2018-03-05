#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"basic view module"
from typing               import Callable, Set, TYPE_CHECKING # pylint: disable=unused-import
from abc                  import ABC
from concurrent.futures   import ThreadPoolExecutor

from bokeh.document       import Document
from bokeh.models.widgets import Button
from bokeh.themes         import Theme
from bokeh.layouts        import layout

from tornado.ioloop             import IOLoop
from tornado.platform.asyncio   import to_tornado_future

from control.action import ActionDescriptor, Computation, Action

if TYPE_CHECKING:
    from .keypress import DpxKeyEvent # pylint: disable=unused-import

SINGLE_THREAD = False

class View(ABC):
    "Classes to be passed a controller"
    action      = ActionDescriptor(Action)
    computation = ActionDescriptor(Computation)
    def __init__(self, **kwargs):
        "initializes the gui"
        self._ctrl = kwargs['ctrl']

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
        if hasattr(ite, 'frozen'): # pylint: disable=simplifiable-if-statement
            ite.frozen   = True
        else:
            ite.disabled = True

    def _onproject(items, __lst__ = itms):
        if 'track' in items:
            val = items['track'].value is items.empty
            for ite in __lst__:
                if hasattr(ite, 'frozen'):
                    ite.frozen   = val
                else:
                    ite.disabled = val
    getattr(ctrl, '_ctrl', ctrl).globals.project.observe(_onproject)

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

def defaultsizingmode(self, kwa:dict = None, **kwargs) -> dict:
    "the default sizing mode"
    if kwa is None:
        kwa = kwargs
    else:
        kwa.update(kwargs)

    css = getattr(self, 'css', None)
    if css is None:
        css = getattr(self, '_ctrl').globals.css
    kwa['sizing_mode'] = css.sizing_mode.get()
    return kwa

class BokehView(View):
    "A view with a gui"
    __CTRL = set() # type: Set[int]
    def __init__(self, **kwargs):
        "initializes the gui"
        super().__init__(**kwargs)
        css = self._ctrl.globals.css
        if id(self._ctrl) not in BokehView.__CTRL:
            BokehView.__CTRL.add(id(self._ctrl))
            css.button.defaults = {'width': 90, 'height': 20}
            css.input .defaults = {'width': 90, 'height': 20}
            css.defaults        = {'sizing_mode': 'fixed'}

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

        self._keys: 'DpxKeyEvent'   = kwargs.get('keys', None)
        self._doc:  Document        = None

    def close(self):
        "closes the application"
        super().close()
        self._doc  = None
        if self._keys is not None:
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
        theme = self._ctrl.globals.css.theme.get(default = None)
        if isinstance(theme, str):
            theme = self._ctrl.globals.css.theme[theme].get(default = None)
        if theme is not None:
            doc.theme = Theme(json = theme)

        self._doc = doc
        if self._keys is not None:
            self._keys.getroots(doc)
        roots = self.getroots(doc)
        while isinstance(roots, (tuple, list)) and len(roots) == 1:
            roots = roots[0]

        if not isinstance(roots, (tuple, list)):
            roots = (roots,)

        if isinstance(roots, (tuple, list)) and len(roots) == 1:
            doc.add_root(roots[0])
        else:
            doc.add_root(layout(roots, **self.defaultsizingmode()))

    def getroots(self, doc):
        "returns object root"
        self._doc = doc

    def button(self, fcn:Callable, title:str, prefix = 'keypress', **kwa):
        "creates and connects a button"
        kwa.setdefault('label',  title.capitalize())
        kwa.setdefault('width',  self._ctrl.globals.css.button.width)
        kwa.setdefault('height', self._ctrl.globals.css.button.height)

        btn = Button(**kwa)
        btn.on_click(fcn)
        if self._keys is not None:
            self._keys.addKeyPress((prefix+'.'+title.lower(), fcn))
        return btn

    def defaultsizingmode(self, kwa = None, **kwargs) -> dict:
        "the default sizing mode"
        return defaultsizingmode(self, kwa, **kwargs)
