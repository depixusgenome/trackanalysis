#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"basic view module"
from typing               import Callable, Set, TYPE_CHECKING # pylint: disable=unused-import
from abc                  import ABC
from concurrent.futures   import ThreadPoolExecutor
from asyncio              import wrap_future

from bokeh.document       import Document

from tornado.ioloop           import IOLoop
from control.action           import ActionDescriptor

if TYPE_CHECKING:
    from .keypress import DpxKeyEvent # pylint: disable=unused-import

SINGLE_THREAD = False

class View(ABC):
    "Classes to be passed a controller"
    action      = ActionDescriptor()
    computation = ActionDescriptor()
    def __init__(self, ctrl = None, **_):
        "initializes the gui"
        self._ctrl = ctrl

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
    return await wrap_future(pool.submit(fcn, *args, **kwa))

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

    theme = getattr(self, 'theme', None)
    if theme is None:
        theme = getattr(self, '_ctrl', ctrl).theme
    kwa['sizing_mode'] = theme.get('main', 'sizingmode', 'fixed')
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
        self._doc:  Document        = None

    def close(self):
        "closes the application"
        super().close()
        self._doc  = None

    def enableOnTrack(self, *itms):
        "Enables/disables view elements depending on the track status"
        enableOnTrack(self._ctrl, *itms)

    def addtodoc(self, _, doc):
        "Adds one's self to doc"
        self._doc = doc

    def defaultsizingmode(self, kwa = None, **kwargs) -> dict:
        "the default sizing mode"
        return defaultsizingmode(self, kwa, **kwargs)
