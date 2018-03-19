#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"basic view module"
from typing               import Callable, Set, TYPE_CHECKING # pylint: disable=unused-import
from abc                  import ABC
from concurrent.futures   import ThreadPoolExecutor

from bokeh.document       import Document
from bokeh.themes         import Theme
from bokeh.layouts        import layout

from tornado.ioloop           import IOLoop
from tornado.platform.asyncio import to_tornado_future
from control.action           import ActionDescriptor

if TYPE_CHECKING:
    from .keypress import DpxKeyEvent # pylint: disable=unused-import

SINGLE_THREAD = False

class View(ABC):
    "Classes to be passed a controller"
    action      = ActionDescriptor()
    computation = ActionDescriptor()
    def __init__(self, **kwargs):
        "initializes the gui"
        self._ctrl = kwargs['ctrl']

    def observe(self, ctrl):
        "whatever needs to be initialized"

    def ismain(self, ctrl):
        "Allows setting-up stuff only when the view is the main one"

    def close(self):
        "closes the application"

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

def defaultsizingmode(self, kwa:dict = None, ctrl = None, **kwargs) -> dict:
    "the default sizing mode"
    if kwa is None:
        kwa = kwargs
    else:
        kwa.update(kwargs)

    css = getattr(self, 'css', None)
    if css is None:
        css = getattr(self, '_ctrl', ctrl).globals.css
    kwa['sizing_mode'] = css.sizing_mode.get()
    return kwa

class BokehView(View):
    "A view with a gui"
    __CTRL = set() # type: Set[int]
    def __init__(self, ctrl = None, **kwargs):
        "initializes the gui"
        super().__init__(ctrl = ctrl, **kwargs)
        css = ctrl.globals.css
        if id(ctrl) not in BokehView.__CTRL:
            BokehView.__CTRL.add(id(ctrl))
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
        self._doc:  Document        = None

    def close(self):
        "closes the application"
        super().close()
        self._doc  = None

    def enableOnTrack(self, *itms):
        "Enables/disables view elements depending on the track status"
        enableOnTrack(self._ctrl, *itms)

    def addtodoc(self, ctrl, doc):
        "Adds one's self to doc"
        theme = ctrl.globals.css.theme.get(default = None)
        if isinstance(theme, str):
            theme = ctrl.globals.css.theme[theme].get(default = None)
        if theme is not None:
            doc.theme = Theme(json = theme)

        self._doc = doc
        roots     = self.getroots(ctrl, doc)
        while isinstance(roots, (tuple, list)) and len(roots) == 1:
            roots = roots[0]

        if not isinstance(roots, (tuple, list)):
            roots = (roots,)

        if isinstance(roots, (tuple, list)) and len(roots) == 1:
            doc.add_root(roots[0])
        else:
            doc.add_root(layout(roots, **self.defaultsizingmode()))

    def getroots(self, _, doc):
        "returns object root"
        self._doc = doc

    def defaultsizingmode(self, kwa = None, **kwargs) -> dict:
        "the default sizing mode"
        return defaultsizingmode(self, kwa, **kwargs)
