#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Basics for threading displays"
from    abc                 import abstractmethod, ABC
from    collections         import OrderedDict
from    contextlib          import contextmanager
from    enum                import Enum
from    time                import time
from    typing              import TypeVar, Generic, cast

from    bokeh.document      import Document
from    bokeh.models        import Model

from    utils.logconfig     import getLogger
from    utils.inspection    import templateattribute as _tattr
from    .base               import threadmethod, spawn, SINGLE_THREAD

LOGS    = getLogger(__name__)

class DisplayState(Enum):
    "plot state"
    active       = 'active'
    abouttoreset = 'abouttoreset'
    resetting    = 'resetting'
    disabled     = 'disabled'
    outofdate    = 'outofdate'

class BaseModel(ABC):
    "basic display model"
    def reset(self, _):
        "resets the model"

    def clear(self):
        "clear the model"

MODEL   = TypeVar('MODEL', bound = BaseModel)
DISPLAY = TypeVar("DISPLAY")
THEME   = TypeVar("THEME")
class DisplayModel(Generic[DISPLAY, THEME], BaseModel):
    "Basic model for time series"
    display: DISPLAY
    theme:   THEME
    def __init__(self, **kwa):
        super().__init__()
        self.display = cast(DISPLAY, _tattr(self, 0)(**kwa))
        self.theme   = cast(THEME,   _tattr(self, 1)(**kwa))

    def observe(self, ctrl) -> bool:
        """
        observe the controller
        """
        if self.theme in ctrl.theme:
            return True
        ctrl.theme.add(self.theme)
        ctrl.display.add(self.display)
        return False

class _OrderedDict(OrderedDict):
    def __missing__(self, key):
        value: dict = OrderedDict()
        self[key]   = value
        return value

class ThreadedDisplay(Generic[MODEL]): # pylint: disable=too-many-public-methods
    "Base plotter class"
    def __init__(self, model: MODEL = None, **kwa) -> None:
        "sets up this plotter's info"
        super().__init__()
        self._model: MODEL   = _tattr(self, 0)(**kwa) if model is None else model
        self._doc:  Document = None
        self.state           = DisplayState.active

    def action(self, ctrl, fcn = None):
        "decorator which starts a user action but only if state is set to active"
        test   = lambda *_1, **_2: self.state is DisplayState.active
        action = ctrl.action.type(ctrl, test = test)
        return action if fcn is None else action(fcn)

    def delegatereset(self, ctrl, cache):
        "Stops on_change events for a time"
        old, self.state = self.state, DisplayState.resetting
        try:
            self._reset(ctrl, cache)
        finally:
            self.state     = old

    @contextmanager
    def resetting(self):
        "Stops on_change events for a time"
        mdls            = _OrderedDict()
        old, self.state = self.state, DisplayState.resetting
        i = j = None
        try:
            yield mdls
            for i, j in mdls.items():
                if isinstance(i, Model):
                    i.update(**j)
                elif callable(j):
                    j()
                else:
                    raise TypeError(f"No know way to update {i} = {j}")

        except ValueError as exc:
            if i is not None:
                raise ValueError(f'Error updating {i} = {j}') from exc
            else:
                raise ValueError(f'Error updating') from exc
        finally:
            self.state = old

    def close(self):
        "Removes the controller"
        del self._model
        del self._ctrl
        del self._doc

    def ismain(self, _):
        "Set-up things if this view is the main one"

    def addtodoc(self, ctrl, doc):
        "returns the figure"
        self._doc = doc
        with self.resetting():
            return self._addtodoc(ctrl, doc)

    def activate(self, ctrl, val):
        "activates the component: resets can occur"
        old        = self.state
        self.state = DisplayState.active if val else DisplayState.disabled
        if val and (old is DisplayState.outofdate):
            self.__doreset(ctrl)

    def reset(self, ctrl, clear: bool = False):
        "Updates the data"
        if clear is True:
            self._model.clear()

        state = self.state
        if   state is DisplayState.disabled:
            self.state = DisplayState.outofdate

        elif state is DisplayState.active:
            self.__doreset(ctrl)

        elif state is DisplayState.abouttoreset:
            with self.resetting():
                self._model.reset(ctrl)

    if SINGLE_THREAD: # pylint: disable=using-constant-test
        # use this for single-thread debugging
        LOGS.info("Running in single-thread mode")
        def __doreset(self, ctrl):
            start = time()
            with self.resetting() as cache:
                self._model.reset(ctrl)
                self._reset(ctrl, cache)
            LOGS.debug("%s.reset done in %.3f", type(self).__qualname__, time() - start)
    else:
        def __doreset(self, ctrl):
            with self.resetting():
                self._model.reset(ctrl)

            old, self.state = self.state, DisplayState.abouttoreset
            spawn(self._reset_and_render, ctrl, old)

        async def _reset_and_render(self, ctrl, old):
            start = time()
            cache = _OrderedDict()
            await threadmethod(self._reset_without_render, ctrl, old, cache)

            msg = "%s.reset done in %.3f", type(self).__qualname__, time() - start
            if cache:
                self._doc.add_next_tick_callback(lambda: self._render(ctrl, cache, msg))
            else:
                LOGS.debug(*msg)

        def _reset_without_render(self, ctrl, old, cache):
            try:
                self.state = DisplayState.resetting
                with ctrl.computation.type(ctrl, calls = self.__doreset):
                    self._reset(ctrl, cache)
            finally:
                self.state = old
            return cache

        def _render(self, ctrl, cache, msg):
            start = time()
            try:
                if cache:
                    with ctrl.computation.type(ctrl, calls = self.__doreset):
                        with self.resetting() as inp:
                            inp.update(cache)
            finally:
                LOGS.debug(msg[0]+"+%.3f", *msg[1:], time() - start)

    @abstractmethod
    def _addtodoc(self, ctrl, doc):
        "creates the plot structure"

    @abstractmethod
    def _reset(self, ctrl, cache):
        "initializes the plot for a new file"
