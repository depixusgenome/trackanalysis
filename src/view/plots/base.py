#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing                  import (Tuple, Optional, Type, Union, Any, Generic,
                                        Dict, TypeVar, List, Iterable, cast)
from    collections             import OrderedDict
from    abc                     import abstractmethod
from    contextlib              import contextmanager
from    functools               import wraps
from    time                    import time
from    threading               import RLock
import  warnings

import  numpy        as     np

import  bokeh.palettes
import  bokeh.models.glyphs     as     _glyphs
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

_CNV  = {'dark_minimal':  'dark',
         'caliber':       'basic',
         'light_minimal': 'basic',
         'light':         'basic',
         'customlight':   'basic',
         'customdark':    'dark'}
def themed(theme, obj, dflt = '--none--'):
    "return the value for the given theme"
    if not isinstance(obj, dict):
        return obj

    theme = getattr(theme, "_model",    theme)
    theme = getattr(theme, "themename", theme)
    return (obj[theme]                   if theme in obj              else
            obj[_CNV.get(theme, 'dark')] if dflt == '--none--'        else
            obj.get(_CNV.get(theme, None), dflt))

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
    @staticmethod
    def __elems(inst):
        ctrl = getattr(inst, '_ctrl').display
        mdl  = getattr(inst, '_plotmodel').display.name
        return ctrl, mdl

    def __get__(self, inst, owner):
        if inst is None:
            return self
        ctrl, mdl = self.__elems(inst)
        return ctrl.model(mdl).state

    @classmethod
    def setdefault(cls, inst, value):
        "sets the default value"
        ctrl, mdl = cls.__elems(inst)
        ctrl.updatedefaults(mdl, state = PlotState(value))

    def __set__(self, inst, value):
        ctrl, mdl = self.__elems(inst)
        ctrl.update(mdl, state = PlotState(value))

class _ModelDescriptor:
    _name: str
    _ctrl: str
    def __set_name__(self, _, name):
        self._name = name[1:]
        self._ctrl = 'display' if name.endswith('display') else 'theme'

    def ctrl(self, inst):
        "return the controller"
        return getattr(getattr(inst, '_ctrl'), self._ctrl)

    def update(self, inst, **value):
        "update the model"
        mdl = self.mdl(inst)
        if mdl is not None:
            return self.ctrl(inst).update(mdl, **value)
        raise AttributeError(f"no such model: {self._name}")

    def mdl(self, inst):
        "return the model"
        mdl = getattr(getattr(inst, '_plotmodel'), self._name, None)
        return None if mdl is None else mdl.name

    def __get__(self, inst, owner):
        if inst is None:
            return self

        mdl = self.mdl(inst)
        return None if mdl is None else self.ctrl(inst).model(mdl)

    def __set__(self, inst, value):
        mdl = self.mdl(inst)
        if mdl is not None:
            return self.ctrl(inst).update(mdl, **value)
        raise AttributeError(f"no such model: {self._name}")

class PlotAttrsView(PlotAttrs):
    "implements PlotAttrs"
    def __init__(self, attrs:PlotAttrs)->None:
        super().__init__(**attrs.__dict__)

    def listpalette(self, count, indexes = None, theme = None) -> List[str]:
        "yields PlotAttrs with colors along the palette provided"
        if self.palette is None:
            raise AttributeError()
        if theme is not None:
            palette = getattr(bokeh.palettes, themed(theme, self.palette), None)
        else:
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

    @staticmethod
    def _alpha(args, prefix = ('line', 'fill'), name = 'alpha'):
        for j in ('', 'nonselection_', 'selection_'):
            if j+name in args:
                alpha = args.pop(j+name)
                for i in prefix:
                    args.setdefault(j+i+'_'+name, alpha)

    @classmethod
    def _coloralpha(cls, args, prefix = ('line', 'fill')):
        if args['color']:
            cls._alpha(args, prefix = prefix, name = 'color')
        else:
            args.pop('color', None)
        cls._alpha(args, prefix = prefix)

    @classmethod
    def _text(cls, args):
        cls._default(args)
        args.pop('size',   None)
        args.pop('radius', None)
        cls._coloralpha(args, prefix = ('text',))

    @classmethod
    def _circle(cls, args):
        cls._triangle(args)
        if 'radius' in args:
            args.pop('size')

    @classmethod
    def _line(cls, args):
        cls._default(args)
        cls._coloralpha(args, prefix = ('line',))
        args['line_width'] = args.pop('size')

    @classmethod
    def _patch(cls, args):
        cls._triangle(args)
        args['line_width'] = args.pop('size')

    @classmethod
    def _triangle(cls, args):
        cls._default(args)
        cls._coloralpha(args)

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
        return {i: themed(theme, j) for i, j in args.items()}, themed(theme, self.glyph)

    def reset(self, theme = 'basic', **kwa) -> GlyphRenderer:
        "adds itself to plot: defines color, size and glyph to use"
        return self.__args(theme, kwa)

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
                'sizing_mode':      self.figsize[2],
                'output_backend':   self.output_backend}
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
        fig = figure(**self.figargs(**kwa))
        if self.toolbar.get('hide', False):
            fig.toolbar.autohide = True
        fig.toolbar.logo = None
        return fig

class PlotUpdater(list):
    "updates plot themes"
    @staticmethod
    def __set_range_names(cache, args, view):
        for axis in 'x_range_name', 'y_range_name':
            if axis in args:
                cache[view][axis] = args.pop(axis)
    @staticmethod
    def __split(nsel, args):
        tmp = {}
        key = ('non' if nsel else '')+'selection_'
        for i in set(args):
            if i.startswith(key):
                tmp[i.replace(key, '')] = args.pop(i)
        return tmp

    @staticmethod
    def __update(cache, rend, data, key):
        glyph = getattr(rend, key)
        data  = {i: j for i, j in data.items()
                 if ((isinstance(j, (str, set, tuple, list)) or np.isscalar(j))
                     and getattr(glyph, i) != j)}
        if len(data):
            cache[glyph].update(**data)

    def reset(self, mdl, theme, cache):
        "resets the renderer to the current theme"
        for i, j, k in self:
            args, glyph = PlotAttrsView(getattr(mdl, j)).reset(theme, **k)
            args.pop("palette", None)
            self.__set_range_names(cache, args, i)

            itms = [args, self.__split(True, args), self.__split(False, args)]
            cls  = getattr(_glyphs, getattr(Figure, glyph).__name__)
            if isinstance(i.glyph, cls):
                for itm in zip(itms, ("glyph", "nonselection_glyph", "selection_glyph")):
                    self.__update(cache, i, *itm)
            else:
                for itm in zip(itms, ("glyph", "nonselection_glyph", "selection_glyph")):
                    out  = dict(args)
                    out.update(itm[0])
                    cache[i][itm[1]] = cls(**out)

class AxisOberver:
    "observe an axis"
    def __init__(self, ctrl, fig: Figure, mdl):
        self._fig      = fig
        self._ctrl     = getattr(ctrl, 'display', ctrl)
        self._mdl: str = getattr(mdl, 'name', mdl)
        self._updating = False

    def _get(self, name):
        return self._ctrl.get(self._mdl, name)

    @property
    def _state(self):
        return None if self._updating else self._get('state')

    def _onchangeaxis(self, name):
        if self._state is not PlotState.active:
            return

        axis  = getattr(self._fig, name+'_range')
        if None in (axis.reset_end, axis.reset_start):
            return

        eps   = 1e-3*(axis.reset_end-axis.reset_start)
        rng   = (axis.start if abs(axis.start-axis.reset_start) > eps else None,
                 axis.end   if abs(axis.end-axis.reset_end)     > eps else None)
        out   = {name+'bounds': rng}
        inits = self._get(name+'init')

        self._updating = True
        try:
            if inits != (None, None) and rng == (None, None):
                out[name+'init'] = axis.reset_start, axis.reset_end
                axis.update(reset_start = inits[0], reset_end = inits[1])
            self._ctrl.update(self._mdl, **out)
        finally:
            self._updating = False

    def _onobserveaxis(self, old = None, **_):
        if self._state is not PlotState.active:
            return

        for i in 'xy':
            if i+'bounds' in old:
                vals = self._get(i+'bounds')
                axis = getattr(self._fig, i+'_range')
                axis.update(start = axis.reset_start if vals[0] is None else vals[0],
                            end   = axis.reset_end   if vals[1] is None else vals[1])

    def __call__(self):
        "adds Range callbacks"
        def _set(name):
            fcn  = lambda attr, old, new: self._onchangeaxis(name)
            axis = getattr(self._fig, name+'_range')
            axis.on_change('start', fcn)
            axis.on_change('end',   fcn)
        _set('x')
        _set('y')
        self._ctrl.observe(self._mdl, self._onobserveaxis)

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

    def __init__(self, ctrl,        # pylint: disable=too-many-arguments
                 addto     = True,
                 noerase   = True,
                 model     = None,
                 plotmodel = None, **kwa) -> None:
        "sets up this plotter's info"
        def _cls(i, *j, **k):
            cls = templateattribute(self, i)
            return cls(*j, **k) if cls else None

        self._updater   = PlotUpdater()
        self._ctrl      = ctrl
        self._model     = _cls(0, ctrl)  if model     is None else model
        self._plotmodel = _cls(1, **kwa) if plotmodel is None else plotmodel

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
        theme  = self._model.themename
        colors = getattr(self._theme, 'colors', None)
        if 'color' not in attrs and isinstance(colors, dict):
            val = themed(theme, colors, {}).get(name, None)
            if val is not None:
                attrs['color'] = val
        itm  = PlotAttrsView(getattr(self._theme, name))
        self._updater.append((itm.addto(fig, theme, **attrs), name, attrs))
        return self._updater[-1][0]

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
                @self._doc.add_next_tick_callback
                def _later():
                    widget.update(**fcn())
                    done[0] = False

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
            self._updater.reset(self._theme, self._model.themename, cache)
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

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore',
                                        category = DeprecationWarning,
                                        message  = ".*elementwise == comparison failed;.*")
                for i, j in cache.items():
                    if self.state != PlotState.resetting:
                        break
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

    def newbounds(self, axis, arr) -> dict:
        "Sets the range boundaries"
        over  = self._theme.overshoot
        if len(arr) == 0:
            return OrderedDict(start  = 0., end = 1., bounds = (0., 1.),
                               reset_start = 0., reset_end = 1.)

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

        delta = max(1e-5, (vmax-vmin))*over*.5
        vmin -= delta
        vmax += delta

        curr = getattr(self._display, f'{axis}bounds', (None, None))
        attrs: Dict[str, Any] = OrderedDict(bounds = (vmin, vmax))
        attrs.update(start = vmin if curr[0]  is None else curr[0], # type: ignore
                     end   = vmax if curr[1]  is None else curr[1],
                     reset_start = vmin, reset_end = vmax)
        return attrs

    def setbounds(self, cache:CACHE_TYPE, fig, # pylint: disable=too-many-arguments
                  xarr, yarr, xinit = None, yinit = None):
        "Sets the range boundaries"
        cache[fig.x_range] = self.newbounds('x', xarr)
        cache[fig.y_range] = self.newbounds('y', yarr)

        args: Dict[str, Tuple[Optional[float], Optional[float]]] = {
            'xinit': (None, None),
            'yinit': (None, None)
        }
        if xinit is not None:
            tmp = self.newbounds('x', xinit)
            cache[fig.x_range].update(start = tmp['start'], end = tmp['end'])
            args['xinit'] = tmp['reset_start'], tmp['reset_end']

        if yinit is not None:
            tmp  = self.newbounds('y', yinit)
            cache[fig.y_range].update(start = tmp['start'], end = tmp['end'])
            args['yinit'] = tmp['reset_start'], tmp['reset_end']

        self._ctrl.display.update(self._display, **args)

    def bounds(self, arr):
        "Returns boundaries for a column"
        if len(arr) == 0:
            return 0., 1.

        if isinstance(arr, np.ndarray):
            good  = arr[np.isfinite(arr)]
            vmin  = good.min()
            vmax  = good.max()
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

    def linkmodeltoaxes(self, fig, mdl = None):
        "add observers between both the figure axes and the model"
        AxisOberver(self._ctrl, fig, self._display if mdl is None else mdl)()

    def ismain(self, _):
        "Set-up things if this view is the main one"

    def reset(self, items:bool):
        "Updates the data"
        assert items in (True, False, None)
        if items:
            self._model.clear()

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
                self._updater.reset(self._theme, self._model.themename, cache)
            ctrl.display.handle('rendered', args = {'plot': self})
    else:
        def __doreset(self, ctrl):
            with self.resetting():
                self._model.reset()
            if getattr(self, '_doc', None) is None:
                return

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
                            self._updater.reset(self._theme, self._model.themename, cache)
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
                                  reset = 'Shift- ',
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

    def addtodoc(self, ctrl, doc):
        "adds items to doc"
        super().addtodoc(ctrl, doc)
        return self._plotter.addtodoc(ctrl, doc)
