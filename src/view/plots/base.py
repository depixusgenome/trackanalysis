#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing                  import (Tuple, Optional, Type, Sequence, Union, Any,
                                        Generic, Dict, TypeVar, List, Iterator,
                                        Iterable, cast)
from    collections             import OrderedDict
from    abc                     import abstractmethod
from    contextlib              import contextmanager
from    functools               import wraps
from    time                    import time
from    threading               import RLock

import  numpy        as     np

import  bokeh.palettes
from    bokeh.document          import Document
from    bokeh.models            import Range1d, Model, GlyphRenderer
from    bokeh.plotting          import figure, Figure

from    utils.logconfig         import getLogger
from    utils.inspection        import templateattribute
from    control.modelaccess     import PlotModelAccess
from    model.task.application  import TaskIOTheme
from    model.plots             import (PlotAttrs, PlotState, PlotModel,
                                        PlotDisplay, PlotTheme)
from    ..base                  import (BokehView, threadmethod, spawn,
                                        defaultsizingmode as _defaultsizingmode,
                                        SINGLE_THREAD)
from    ..colors                import tohex
from    .bokehext               import DpxKeyedRow, DpxHoverTool

LOGS        = getLogger(__name__)
ModelType   = TypeVar('ModelType', bound = PlotModelAccess)
RANGE_TYPE  = Tuple[Optional[float], Optional[float]] # pylint: disable=invalid-name
CACHE_TYPE  = Dict[Model, Any]                        # pylint: disable=invalid-name

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
        return getattr(getattr(inst, '_plotmodel'), self._name, None) if inst else self

    def __set__(self, inst, value):
        getattr(inst, '_ctrl').display.update(self.__get__(inst, None), **value)

class PlotAttrsView(PlotAttrs):
    "implements PlotAttrs"
    def __init__(self, attrs:PlotAttrs)->None:
        super().__init__(**attrs.__dict__)

    def iterpalette(self, count, *tochange, indexes = None) -> Iterator['PlotAttrs']:
        "yields PlotAttrs with colors along the palette provided"
        if self.palette is None:
            raise AttributeError()
        info    = dict(self.__dict__)
        palette = getattr(bokeh.palettes, self.palette, None)

        if palette is None:
            for _ in range(count):
                yield PlotAttrs(**info)
            return

        colors = palette(count)
        if indexes is not None:
            colors = [colors[i] for i in indexes]

        if len(tochange) == 0:
            tochange = ('color',)

        for color in colors:
            info.update((name, color) for name in tochange)
            yield PlotAttrs(**info)

    def listpalette(self, count, indexes = None) -> List[str]:
        "yields PlotAttrs with colors along the palette provided"
        if self.palette is None:
            raise AttributeError()
        palette = getattr(bokeh.palettes, self.palette, None)
        if palette is None:
            return [self.color]*count
        if isinstance(palette, dict):
            colors: List[str] = max(palette.values(), key = len)
            npal   = len(colors)
            if indexes is None:
                return [colors[int(i/count*npal)] for i in range(count)]
            indexes    = tuple(indexes)
            minv, maxv = min(indexes), max(indexes)
            return [colors[int((i-minv)/(maxv-minv)*npal)] for i in indexes]
        colors  = palette(count)
        return [colors[i] for i in indexes] if indexes is not None else colors

    @classmethod
    def _text(cls, args):
        cls._default(args)
        args.pop('size',   None)
        args.pop('radius', None)
        args['text_color'] = args.pop('color')

    @classmethod
    def _circle(cls, args):
        cls._default(args)
        if 'radius' in args:
            args.pop('size')
        clr = args.pop('color')
        if clr:
            for i in ('line_color', 'fill_color'):
                args.setdefault(i, clr)

    @classmethod
    def _line(cls, args):
        cls._default(args)
        if 'color' in args:
            args['line_color'] = args.pop('color')
        args['line_width'] = args.pop('size')

    @classmethod
    def _patch(cls, args):
        cls._triangle(args)
        args['line_width'] = args.pop('size')

    @classmethod
    def _triangle(cls, args):
        cls._default(args)
        clr = args.pop('color')
        if clr:
            for i in ('line_color', 'fill_color'):
                args.setdefault(i, clr)

    _diamond  = _triangle
    _vbar     = _patch
    _quad     = _line

    @classmethod
    def _rect(cls, args):
        cls._default(args)
        args.pop('size')

    @staticmethod
    def _image(args):
        color = args.pop('color')
        args.pop('size')
        if args['palette'] is None:
            args['palette'] = color

    @staticmethod
    def _default(args):
        args.pop('palette')

    def __args(self, theme, kwa):
        args = dict(self.__dict__)
        args.pop('glyph')
        args.update(kwa)
        getattr(self, '_'+self.glyph, self._default)(args)
        args  = {i: j[theme] if isinstance(j, dict) else j for i, j in args.items()}
        glyph = self.glyph[theme] if isinstance(self.glyph, dict) else self.glyph
        return args, glyph

    def addto(self, fig, theme = 'basic', **kwa) -> GlyphRenderer:
        "adds itself to plot: defines color, size and glyph to use"
        args, glyph = self.__args(theme, kwa)
        return getattr(fig, glyph)(**args)

    def setcolor(self, rend, cache = None, theme = None, **kwa):
        "sets the color"
        args   = self.__args(theme, kwa)[0]
        colors = {}
        for i, j in args.items():
            if 'color' not in i:
                continue
            try:
                colors[i] = tohex(j)
            except AttributeError:
                pass

        if cache is None:
            rend.glyph.update(**colors)
        else:
            cache[rend.glyph].update(**colors)

class PlotThemeView(PlotTheme):
    "implements PlotTheme"
    def __init__(self, attrs:PlotTheme)->None:
        super().__init__(**attrs.__dict__)

    def figargs(self, **kwa) -> Dict[str, Any]:
        "create a figure"
        tips = kwa.pop('tooltips', self.tooltips)
        args = {'toolbar_sticky':   self.toolbar['sticky'],
                'toolbar_location': self.toolbar['location'],
                'tools':            self.toolbar['items'],
                'x_axis_label':     self.xlabel,
                'y_axis_label':     self.ylabel,
                'plot_width':       self.figsize[0],
                'plot_height':      self.figsize[1],
                'sizing_mode':      self.figsize[2]}
        args.update(kwa)

        tools:list = []
        if isinstance(args['tools'], str):
            tools = cast(str, args['tools']).split(',')
        elif not args['tools']:
            tools = []
        else:
            tools = cast(List[Any], args['tools'])

        if 'dpxhover' in tools:
            hvr   = DpxHoverTool(tooltips = tips) if tips else DpxHoverTool()
            tools = [i if i != 'dpxhover' else hvr for i in tools]

        args['tools'] = tools

        for name in ('x_range', 'y_range'):
            if args.get(name, None) is Range1d:
                args[name] = Range1d(start = 0., end = 1.)
        return args

    def figure(self, **kwa) -> Figure:
        "creates a figure"
        return figure(**self.figargs(**kwa))

class PlotCreator(Generic[ControlModelType, PlotModelType]): # pylint: disable=too-many-public-methods
    "Base plotter class"
    _RESET   = frozenset(('bead',))
    _CLEAR   = frozenset(('track',))
    state    = cast(PlotState,   _StateDescriptor())
    _theme   = cast(PlotTheme,   _ModelDescriptor())
    _display = cast(PlotDisplay, _ModelDescriptor())
    _config  = cast(Any,         _ModelDescriptor())
    _doc      : Document
    _model    : ControlModelType
    _plotmodel: Optional[PlotModelType]
    class _OrderedDict(OrderedDict):
        def __missing__(self, key):
            value: Dict = OrderedDict()
            self[key]   = value
            return value

    def __init__(self, ctrl, addto = True, noerase = True) -> None:
        "sets up this plotter's info"
        def _cls(i, *j):
            cls = templateattribute(self, i)
            return cls(*j) if cls else None

        self._ctrl      = ctrl
        self._model     = _cls(0, ctrl)
        self._plotmodel = _cls(1)

        if addto:
            self.addto(ctrl, noerase = noerase)

    @staticmethod
    def attrs(attrs:PlotAttrs) -> PlotAttrsView:
        "shortcuts for PlotAttrsView"
        return PlotAttrsView(attrs)

    @staticmethod
    def fig(attrs:PlotTheme) -> PlotThemeView:
        "shortcuts for PlotThemeView"
        return PlotThemeView(attrs)

    def setcolor(self, name:Union[str, Iterable[Tuple[str, Any]]], rend = None, **attrs):
        "shortcuts for PlotThemeView"
        if isinstance(name, str):
            assert rend is not None
            PlotAttrsView(getattr(self._theme, name)).setcolor(rend, **attrs)
        else:
            for i, j in name:
                PlotAttrsView(getattr(self._theme, i)).setcolor(j, **attrs)

    def addtofig(self, fig, name, **attrs) -> GlyphRenderer:
        "shortcuts for PlotThemeView"
        theme = self._model.themename
        if ('color' not in attrs
                and isinstance(getattr(self._theme, 'colors', None), dict)
                and name in getattr(self._theme, 'colors').get(theme, {})):
            attrs['color'] = getattr(self._theme, 'colors')[theme][name]
        return PlotAttrsView(getattr(self._theme, name)).addto(fig, theme, **attrs)

    def figure(self, **attrs) -> Figure:
        "shortcuts for PlotThemeView"
        return PlotThemeView(self._theme).figure(**attrs)

    def addto(self, ctrl, noerase = True):
        "adds the models to the controller"
        if self._plotmodel:
            self._plotmodel.addto(ctrl, noerase = noerase)
        if self._model:
            self._model.addto(ctrl, noerase = noerase)

    def defaultsizingmode(self, kwa = None, **kwargs):
        "the default sizing mode"
        return _defaultsizingmode(self, kwa = kwa, **kwargs)

    def isactive(self, *_1, **_2) -> bool:
        "whether the state is set to active"
        return self.state == PlotState.active

    def calllater(self, fcn):
        "calls a method later"
        self._doc.add_next_tick_callback(fcn)

    def differedobserver(self, fcn, widget, *args):
        "creates a method to update widgets later"
        if callable(getattr(fcn, "update", None)):
            fcn, widget = widget, fcn

        if not callable(getattr(widget, "update", None)):
            raise ValueError()

        done = [False]
        def _observer(**_):
            if self.isactive() and not done[0]:
                done[0] = True
                data    = fcn()
                @self._doc.add_next_tick_callback
                def _later():
                    widget.update(**data)
                    done[0] = True

        if len(args) % 2 != 0:
            raise ValueError()

        for i in range(0, len(args), 2):
            if callable(getattr(args[i], 'observe', None)):
                args[i].observe(args[i+1], _observer)
            else:
                args[i+1].observe(args[i], _observer)
        return _observer

    def actionifactive(self, ctrl):
        u"decorator which starts a user action but only if state is set to active"
        return ctrl.action.type(ctrl, test = self.isactive)

    def action(self, fcn = None):
        u"decorator which starts a user action but only if state is set to active"
        action = BokehView.action.type(self._ctrl, test = self.isactive)
        return action if fcn is None else action(fcn)

    def delegatereset(self, cache:CACHE_TYPE):
        "Stops on_change events for a time"
        old, self.state = self.state, PlotState.resetting
        try:
            self._reset(cache)
        finally:
            self.state     = old

    _LOCK = RLock()

    @contextmanager
    def resetting(self, cache = None):
        "Stops on_change events for a time"
        try:
            self._LOCK.acquire()
            old, self.state = self.state, PlotState.resetting
            i = j = None
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
            if self.state == PlotState.resetting:
                self.state = old
            self._LOCK.release()

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
                     end   = vmax if curr[1]  is None else curr[1],
                     reset_start = vmin, reset_end = vmax)
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
                self.calllater(_render)

            spawn(_reset_and_render)

    def _keyedlayout(self, ctrl, main, *figs, left = None, bottom = None, right = None):
        return DpxKeyedRow.keyedlayout(ctrl, self, main, *figs,
                                       left   = left,
                                       right  = right,
                                       bottom = bottom,)

    def observe(self, ctrl, noerase = False):
        "sets-up model observers"
        if self._plotmodel:
            self._plotmodel.observe(ctrl, noerase)
        @ctrl.theme.observe
        def _onmain(old=None, **_):
            if 'themename' in old:
                self.reset(False)

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
        cnf = ctrl.theme.model("tasks.io", True)
        if cnf is None:
            ctrl.theme.add(TaskIOTheme().setup(tasks, ioopen, iosave), False)
        else:
            diff = cnf.setup(tasks, ioopen, iosave).diff(cnf)
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

    def observestate(self, ctrl, fcn):
        "sets up state observers"
        ctrl.display.observe(getattr(self._plotter, '_display').name, fcn)

    def addtodoc(self, ctrl, doc):
        "adds items to doc"
        super().addtodoc(ctrl, doc)
        return self._plotter.addtodoc(ctrl, doc)
