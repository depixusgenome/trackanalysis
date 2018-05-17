#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing              import (Tuple, Optional, Type, Sequence, Union, Any,
                                    Generic, Dict, TypeVar, cast)
from    collections         import OrderedDict
from    abc                 import abstractmethod
from    contextlib          import contextmanager
from    functools           import wraps
from    time                import time

import  numpy        as     np

from    bokeh.document          import Document
from    bokeh.models            import Range1d, Model, CustomJS

from    utils.logconfig         import getLogger
from    utils.inspection        import templateattribute
from    control.modelaccess     import PlotModelAccess
from    model.task.application  import TaskIOTheme
from    model.plots             import PlotState, PlotModel, PlotDisplay, PlotTheme
from    ..base                  import (BokehView, threadmethod, spawn,
                                        defaultsizingmode as _defaultsizingmode,
                                        SINGLE_THREAD)
from    .bokehext               import DpxKeyedRow

LOGS        = getLogger(__name__)
ModelType   = TypeVar('ModelType', bound = PlotModelAccess)
RANGE_TYPE  = Tuple[Optional[float], Optional[float]]
CACHE_TYPE  = Dict[Model, Any]

def checksizes(fcn):
    "Checks that the ColumnDataSource have same sizes"
    @wraps(fcn)
    def _wrap(*args, **kwa):
        res  = fcn(*args, **kwa)
        if len(res) == 0:
            return res
        size = len(next(iter(res.values())))
        assert all(size == len(i) for i in res.values())
        return res
    return _wrap

PlotModelType    = TypeVar('PlotModelType',    bound = PlotModel)
ControlModelType = TypeVar('ControlModelType', bound = PlotModelAccess)

class _StateDescriptor:
    def __get__(self, inst, owner):
        return getattr(inst, '_plotmodel').display.state if inst else self

    @staticmethod
    def setdefault(inst, value):
        "sets the default value"
        getattr(inst, '_ctrl').display.updatedefaults(getattr(inst, '_plotmodel').display,
                                                      state = PlotState(value))

    def __set__(self, inst, value):
        getattr(inst, '_ctrl').display.update(getattr(inst, '_plotmodel').display,
                                              state = PlotState(value))

class _ModelDescriptor:
    def __init__(self):
        self._name = ''

    def __set_name__(self, _, name):
        self._name  = name[1:]

    def __get__(self, inst, owner):
        return getattr(getattr(inst, '_plotmodel'), self._name) if inst else self

    def __set__(self, inst, value):
        getattr(inst, '_ctrl').display.update(self.__get__(inst, None), **value)

class PlotCreator(Generic[ControlModelType, PlotModelType]): # pylint: disable=too-many-public-methods
    "Base plotter class"
    _RESET   = frozenset(('bead',))
    _CLEAR   = frozenset(('track',))
    state    = cast(PlotState,   _StateDescriptor())
    _theme   = cast(PlotTheme,   _ModelDescriptor())
    _display = cast(PlotDisplay, _ModelDescriptor())
    _config  = cast(Any,         _ModelDescriptor())
    _doc     : Document
    class _OrderedDict(OrderedDict):
        def __missing__(self, key):
            value: Dict = OrderedDict()
            self[key]   = value
            return value

    def __init__(self, ctrl, *_) -> None:
        "sets up this plotter's info"
        key = type(self).key()
        self._model:     ControlModelType = templateattribute(self, 0)(ctrl)
        self._plotmodel: PlotModelType    = templateattribute(self, 1)(name = key)
        self._ctrl                        = ctrl

    def defaultsizingmode(self, kwa = None, **kwargs):
        "the default sizing mode"
        return _defaultsizingmode(self, kwa = kwa, **kwargs)

    @classmethod
    def key(cls):
        "the key to this plot creator"
        name = cls.__name__.lower()
        if 'plot' in name:
            name = name[:name.rfind('plot')]
        return ".plot." + name

    def action(self, fcn = None):
        u"decorator which starts a user action but only if state is set to active"
        test   = lambda *_1, **_2: self.state is PlotState.active
        action = BokehView.action.type(self._ctrl, test = test)
        return action if fcn is None else action(fcn)

    def delegatereset(self, cache:CACHE_TYPE):
        "Stops on_change events for a time"
        old, self.state = self.state, PlotState.resetting
        try:
            self._reset(cache)
        finally:
            self.state     = old

    @contextmanager
    def resetting(self, cache = None):
        "Stops on_change events for a time"
        old, self.state = self.state, PlotState.resetting
        i = j = None
        try:
            if cache is None:
                cache = self._OrderedDict()
            yield cache
            for i, j in cache.items():
                try:
                    upd = getattr(i, 'update', None)
                    if upd is None:
                        if callable(j):
                            j(i)
                        else:
                            LOGS.warning("incorrect bk update (%s, %s)", i, j)
                    else:
                        upd(**j)
                except ValueError as exc:
                    raise ValueError(f'Error updating {i} = {j}') from exc
                except Exception as exc:
                    raise RuntimeError(f'Error updating {i} = {j}') from exc
        finally:
            self.state = old

    @staticmethod
    def fixreset(arng):
        "Corrects the reset bug in bokeh"
        assert isinstance(arng, Range1d)
        jsc = CustomJS(code = ("if(!(cb_obj.bounds == null))"
                               "{ cb_obj._initial_start = cb_obj.bounds[0];"
                               "  cb_obj._initial_end   = cb_obj.bounds[1]; }"))
        arng.callback = jsc

    def close(self):
        "Removes the controller"
        del self._ctrl
        del self._doc

    def newbounds(self, rng, axis, arr) -> dict:
        "Sets the range boundaries"
        over  = self._theme.overshoot

        if isinstance(arr, np.ndarray):
            if all(np.isnan(i) for i in arr) or len(arr) == 0:
                vmin = 0.
                vmax = 1.
            else:
                vmin = np.nanmin(arr)
                vmax = np.nanmax(arr)
        elif len(arr):
            vmin = min(arr)
            vmax = max(arr)
        else:
            vmin = 0.
            vmax = 1.

        delta = max(1e-5, (vmax-vmin))*over*.5
        vmin -= delta
        vmax += delta

        curr = getattr(self._display, f'{axis}bounds') if axis else (None, None)
        attrs: Dict[str, Any] = OrderedDict(bounds = (vmin, vmax))
        attrs.update(start = vmin if curr[0]  is None else curr[0], # type: ignore
                     end   = vmax if curr[1]  is None else curr[1])
        if hasattr(rng, 'range_padding'):
            attrs['range_padding'] = over*100.

        return attrs

    def setbounds(self, cache:CACHE_TYPE, # pylint: disable=too-many-arguments
                  rng, axis, arr, reinit = True):
        "Sets the range boundaries"
        vals = self.newbounds(rng, axis, arr)
        if reinit and hasattr(rng, 'reinit'):
            vals['reinit'] = not rng.reinit
        cache[rng] = vals

    def bounds(self, arr):
        "Returns boundaries for a column"
        if len(arr) == 0:
            return 0., 1.

        if isinstance(arr, np.ndarray):
            vmin  = np.nanmin(arr)
            vmax  = np.nanmax(arr)
        else:
            vmin  = min(arr)
            vmax  = max(arr)

        delta = (vmax-vmin)*self._theme.overshoot
        vmin -= delta
        vmax += delta
        return vmin, vmax

    def addtodoc(self, ctrl, doc):
        "returns the figure"
        self._doc = doc
        self._model.addtodoc(doc)
        with self.resetting():
            return self._addtodoc(ctrl, doc)

    def activate(self, val):
        "activates the component: resets can occur"
        old        = self.state
        self.state = PlotState.active if val else PlotState.disabled
        if val and (old is PlotState.outofdate):
            self.__doreset(self._ctrl)

    def ismain(self, _):
        "Set-up things if this view is the main one"

    def reset(self, items:Union[bool, Dict[str,Any]]):
        "Updates the data"
        if isinstance(items, bool):
            if items:
                self._model.clear()

        elif not self._CLEAR.isdisjoint(cast(Sequence, items)):
            self._model.clear()

        elif self._RESET.isdisjoint(cast(Sequence, items)):
            return

        state = self.state
        if   state is PlotState.disabled:
            self.state = PlotState.outofdate

        elif state is PlotState.active:
            self.__doreset(self._ctrl)

        elif state is PlotState.abouttoreset:
            with self.resetting():
                self._model.reset()


    if SINGLE_THREAD: # pylint: disable=using-constant-test
        # use this for single-thread debugging
        LOGS.info("Running in single-thread mode")
        def __doreset(self, ctrl):
            with self.resetting() as cache:
                self._model.reset()
                self._reset(cache)
            ctrl.display.handle('rendered', args = {'plot': self})
    else:
        def __doreset(self, ctrl):
            with self.resetting():
                self._model.reset()

            old, self.state = self.state, PlotState.abouttoreset
            durations       = [0.]
            async def _reset_and_render():
                cache = self._OrderedDict()
                def _reset():
                    start = time()
                    self.state = PlotState.resetting
                    with BokehView.computation.type(ctrl, calls = self.__doreset):
                        try:
                            self._reset(cache)
                        except Exception as exc: # pylint: disable=broad-except
                            args = getattr(exc, 'args', tuple())
                            if len(args) == 2 and args[1] == "warning":
                                ctrl.display.update("message", message = exc)
                            else:
                                raise
                        finally:
                            self.state = old
                            durations.append(time() - start)

                await threadmethod(_reset)

                def _render():
                    start = time()
                    if cache:
                        with BokehView.computation.type(ctrl, calls = self.__doreset):
                            with self.resetting(cache):
                                pass
                    ctrl.display.handle('rendered', args = {'plot': self})
                    LOGS.debug("%s.reset done in %.3f+%.3f",
                               type(self).__qualname__, durations[-1], time() - start)
                self._doc.add_next_tick_callback(_render)

            spawn(_reset_and_render)

    def _keyedlayout(self, ctrl, main, *figs, left = None, bottom = None, right = None):
        return DpxKeyedRow.keyedlayout(ctrl, self, main, *figs,
                                       left   = left,
                                       right  = right,
                                       bottom = bottom,)

    def observe(self, ctrl):
        "sets-up model observers"
        if self._plotmodel:
            self._plotmodel.observe(ctrl)

    @abstractmethod
    def _addtodoc(self, ctrl, doc):
        "creates the plot structure"

    @abstractmethod
    def _reset(self, cache:CACHE_TYPE):
        "initializes the plot for a new file"

PlotType = TypeVar('PlotType', bound = PlotCreator)
class PlotView(Generic[PlotType], BokehView):
    "plot view"
    def __init__(self, ctrl = None, **kwa):
        super().__init__(ctrl, **kwa)

        def _gesture(name, meta):
            return {name+'rate'    : .2,
                    name+'activate': meta[:-1],
                    name+'xlow'    : meta+'ArrowLeft',
                    name+'xhigh'   : meta+'ArrowRight',
                    name+'ylow'    : meta+'ArrowDown',
                    name+'yhigh'   : meta+'ArrowUp'}

        ctrl.theme.updatedefaults('keystroke',
                                  reset = 'Shift -',
                                  **_gesture('pan', 'Alt-'),
                                  **_gesture('zoom', 'Shift-'))
        self._plotter = self.plottype()(ctrl)

    @classmethod
    def plottype(cls) -> Type[PlotCreator]:
        "the model class object"
        return cast(Type[PlotCreator], templateattribute(cls, 0))

    @property
    def plotter(self):
        "returns the plot creator"
        return self._plotter

    def _ismain(self, ctrl, tasks = None, ioopen = None, iosave = None):
        "Set-up things if this view is the main one"
        self._plotter.ismain(ctrl)
        cnf = ctrl.theme.model("taskio", True)
        if cnf is None:
            ctrl.theme.add(TaskIOTheme().setup(tasks, ioopen, iosave))
        else:
            diff = cnf.diff(cnf.setup(tasks, ioopen, iosave))
            if diff:
                ctrl.theme.updatedefaults(cnf, **diff)

    def close(self):
        "remove controller"
        super().close()
        self._plotter.close()
        self._plotter = None

    def activate(self, val):
        "activates the component: resets can occur"
        self._plotter.activate(val)

    def observe(self, ctrl):
        "sets up observers"
        self._plotter.observe(ctrl)

    def addtodoc(self, ctrl, doc):
        "adds items to doc"
        super().addtodoc(ctrl, doc)
        return self._plotter.addtodoc(ctrl, doc)
