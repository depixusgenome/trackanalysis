#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing              import (Tuple, Optional, Type, # pylint: disable=unused-import
                                    Iterator, Sequence, List, Union, Any,
                                    Generic, Dict, TypeVar, cast)
from    collections         import OrderedDict
from    abc                 import abstractmethod
from    contextlib          import contextmanager
from    functools           import wraps
from    time                import time

import  numpy        as     np

import  bokeh.palettes
from    bokeh.document          import Document
from    bokeh.models            import (Range1d, RadioButtonGroup, Model,
                                        Paragraph, Widget, GlyphRenderer, CustomJS)

from    utils.logconfig         import getLogger
from    utils.inspection        import templateattribute
from    control.modelaccess     import GlobalsAccess, PlotModelAccess, PlotState
from    model.task.application  import TaskIOTheme
from    ..base                  import (BokehView, threadmethod, spawn,
                                        defaultsizingmode as _defaultsizingmode,
                                        SINGLE_THREAD)
from    .bokehext               import DpxHoverTool, DpxKeyedRow

LOGS    = getLogger(__name__)
_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name

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

class PlotAttrs:
    "Plot Attributes for one variable"
    def __init__(self,
                 color        = 'blue',
                 glyph        = 'line',
                 size         = 1,
                 palette: str = None,
                 **kwa) -> None:
        self.color   = color
        self.glyph   = glyph
        self.size    = size
        self.palette = palette
        self.__dict__.update(kwa)

    def iterpalette(self, count, *tochange, indexes = None) -> Iterator['PlotAttrs']:
        "yields PlotAttrs with colors along the palette provided"
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
        palette = getattr(bokeh.palettes, self.palette, None)
        if palette is None:
            return [self.color]*count
        elif isinstance(palette, dict):
            colors = max(palette.values(), key = len) # type: List[str]
            npal   = len(colors)
            if indexes is None:
                return [colors[int(i/count*npal)] for i in range(count)]
            indexes    = tuple(indexes)
            minv, maxv = min(indexes), max(indexes)
            return [colors[int((i-minv)/(maxv-minv)*npal)] for i in indexes]
        else:
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

    @classmethod
    def _line(cls, args):
        cls._default(args)
        args['line_width'] = args.pop('size')

    @classmethod
    def _patch(cls, args):
        cls._default(args)
        clr = args.pop('color')
        if clr:
            for i in ('line_color', 'fill_color'):
                args.setdefault(i, clr)

        args['line_width'] = args.pop('size')

    @classmethod
    def _vbar(cls, args):
        cls._default(args)
        clr = args.pop('color')
        if clr:
            for i in ('line_color', 'fill_color'):
                args.setdefault(i, clr)

        args['line_width'] = args.pop('size')

    _quad = _line

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

    def addto(self, fig, **kwa) -> GlyphRenderer:
        "adds itself to plot: defines color, size and glyph to use"
        args = dict(self.__dict__)
        args.pop('glyph')
        args.update(kwa)
        getattr(self, '_'+self.glyph, self._default)(args)
        return getattr(fig, self.glyph)(**args)

ModelType = TypeVar('ModelType', bound = PlotModelAccess)

class WidgetCreator(GlobalsAccess, Generic[ModelType]):
    "Base class for creating a widget"
    def __init__(self, model:ModelType) -> None:
        super().__init__(model)
        self._model = model
        self._ctrl  = getattr(model, '_ctrl')

    def observe(self, _):
        "sets-up config observers"

    @abstractmethod
    def addtodoc(self, action) -> List[Widget]:
        "Creates the widget"

    @abstractmethod
    def reset(self, resets):
        "resets the wiget when a new file is opened"

class GroupWidget(WidgetCreator[ModelType]):
    "Allows creating group widgets"
    INPUT = RadioButtonGroup
    def __init__(self, model) -> None:
        super().__init__(model)
        self._widget: RadioButtonGroup = None

    def addtodoc(self, action) -> List[Widget]:
        "creates the widget"
        name = self.__class__.__name__.replace('Widget', '').replace('Creator', '')
        css  = self.css.title[name.lower()]
        self._widget = self.INPUT(labels = css.labels.get(),
                                  name   = 'Cycles:'+name,
                                  **self._data())
        self._widget.on_click(action(self.onclick_cb))

        if css.get(default = None) is not None:
            return [Paragraph(text = css.get()), self._widget]
        return [self._widget]

    def reset(self, resets):
        "updates the widget"
        resets[self._widget].update(**self._data())

    @abstractmethod
    def onclick_cb(self, value):
        "action to be performed when buttons are clicked"

    @abstractmethod
    def _data(self) -> dict:
        "returns  a dict of updated widget attributes"

    @abstractmethod
    def observe(self, ctrl):
        "Creates the widget"

class PlotCreator(Generic[ModelType], GlobalsAccess): # pylint: disable=too-many-public-methods
    "Base plotter class"
    _RESET  = frozenset(('bead',))
    _CLEAR  = frozenset(('track',))
    class _OrderedDict(OrderedDict):
        def __missing__(self, key):
            value     = OrderedDict() # type: Dict
            self[key] = value
            return value

    def __init__(self, ctrl, *_) -> None:
        "sets up this plotter's info"
        css = ctrl.globals.css.plot
        if css.ylabel.get(default = None) is None:
            css.defaults = {'ylabel'             : u'Z (μm)',
                            'yrightlabel'        : u'Base number',
                            'xtoplabel'          : u'Time (s)',
                            'xlabel'             : u'Frames',
                            'toolbar_location'   : 'right',
                            'toolbar_sticky'     : False,
                            'input.width'        : 205,
                            'figure.width'       : 800,
                            'figure.height'      : 200}
            css.figure.sizing_mode.default = 'fixed'

        key = type(self).key()
        for name in 'config', 'project', 'css':
            ctrl.globals.addGlobalMap(name+key)

        super().__init__(ctrl, key)
        self._model: ModelType                    = self.modeltype()(ctrl, key)
        self._ctrl                                = ctrl
        self._bkmodels: Dict[Model,Dict[str,Any]] = self._OrderedDict()
        self._doc:      Document                  = None
        self.project.state.default = PlotState.active

    @classmethod
    def modeltype(cls) -> Type[ModelType]:
        "the model class object"
        return cast(Type[ModelType], templateattribute(cls, 0))

    state = cast(PlotState,
                 property(lambda self:    self.project.state.get(),
                          lambda self, i: self.project.state.set(PlotState(i))))

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

    def delegatereset(self, bkmodels):
        "Stops on_change events for a time"
        oldbk           = self._bkmodels
        self._bkmodels  = bkmodels
        old, self.state = self.state, PlotState.resetting
        try:
            self._reset()
        finally:
            self._bkmodels = oldbk
            self.state     = old

    @contextmanager
    def resetting(self):
        "Stops on_change events for a time"
        self._bkmodels.clear()
        old, self.state = self.state, PlotState.resetting
        i = j = None
        try:
            yield self
            for i, j in self._bkmodels.items():
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
            self._bkmodels.clear()
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
        over  = self.css.boundary.overshoot.get()

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

        if axis is None:
            curr = None, None # type: Tuple[Optional[float], Optional[float]]
        else:
            curr = self.project[axis].get(default = (vmin, vmax))

        attrs = OrderedDict(bounds = (vmin, vmax))                  # type: Dict[str, Any]
        attrs.update(start = vmin if curr[0]  is None else curr[0], # type: ignore
                     end   = vmax if curr[1]  is None else curr[1])
        if hasattr(rng, 'range_padding'):
            attrs['range_padding'] = over*100.

        return attrs

    def setbounds(self, rng, axis, arr, reinit = True):
        "Sets the range boundaries"
        vals = self.newbounds(rng, axis, arr)
        if reinit and hasattr(rng, 'reinit'):
            vals['reinit'] = not rng.reinit
        self._bkmodels[rng] = vals

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

        delta = (vmax-vmin)*self.config.boundary.overshoot.get()
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
            with self.resetting():
                self._model.reset()
                self._reset()
            ctrl.handle('rendered', args = {'plot': self})
    else:
        def __doreset(self, ctrl):
            with self.resetting():
                self._bkmodels.clear()
                self._model.reset()

            old, self.state = self.state, PlotState.abouttoreset
            durations       = [0.]
            async def _reset_and_render():
                def _reset():
                    start = time()
                    self.state = PlotState.resetting
                    with BokehView.computation.type(ctrl, calls = self.__doreset):
                        try:
                            self._reset()
                        except Exception as exc: # pylint: disable=broad-except
                            args = getattr(exc, 'args', tuple())
                            if len(args) == 2 and args[1] == "warning":
                                ctrl.globals.project.message.set(exc)
                            else:
                                raise
                        finally:
                            self.state = old
                            durations.append(time() - start)

                await threadmethod(_reset)

                def _render():
                    start = time()
                    ret   = tuple(self._bkmodels.items())
                    self._bkmodels.clear()
                    if ret:
                        with BokehView.computation.type(ctrl, calls = self.__doreset):
                            with self.resetting():
                                self._bkmodels.update(ret)
                    ctrl.handle('rendered', args = {'plot': self})
                    LOGS.debug("%s.reset done in %.3f+%.3f",
                               type(self).__qualname__, durations[-1], time() - start)
                self._doc.add_next_tick_callback(_render)

            spawn(_reset_and_render)

    def _addcallbacks(self, fig):
        "adds Range callbacks"
        updating = [False]
        def _get(attr):
            axis = getattr(fig, attr+'_range')
            cnf  = getattr(self.project, attr)

            def _on_cb(attr, old, new):
                if self.state is PlotState.active:
                    vals = axis.start, axis.end # type: tuple
                    if axis.bounds is not None:
                        rng = 1e-3*(axis.bounds[1]-axis.bounds[0])
                        vals = tuple(None if abs(i-j) < rng else j
                                     for i, j in zip(axis.bounds, vals))
                    updating[0] = True
                    cnf.set(vals)
                    updating[0] = False

            cnf.default = None, None
            axis.on_change('start', _on_cb)
            axis.on_change('end',   _on_cb)

        _get('x')
        _get('y')

        def _onobserve(items):
            if updating[0]:
                return
            for i in {'x', 'y'} & frozenset(items):
                rng  = getattr(fig, i+'_range')
                vals = items[i].value
                bnds = rng.bounds
                rng.update(start = bnds[0] if vals[0] is None else vals[0],
                           end   = bnds[1] if vals[1] is None else vals[1])

        self.project.observe('x', 'y', _onobserve)
        return fig

    def _sizing(self, *attrs, translations = None, css = None, **kwa) -> dict:
        "returns keys for sizing"
        if css is None:
            cssarr = (self.config,) + (self.css,)
        elif isinstance(css, (tuple, list)):
            cssarr = (self.config,) + tuple(css) + (self.css,)
        else:
            cssarr = (self.config,) + (css,) + (self.css,)

        if translations is None:
            translations = {}

        args = {}
        for name in attrs:
            for dico in cssarr:
                val = dico.get(name, default = _m_none)
                if val is not _m_none:
                    args[translations.get(name, name)] = val
                    break

        args.update((translations.get(i, i), j) for i, j in kwa.items())
        return args

    def _figargs(self, *cssarr, **kwa) -> dict:
        trans = {'toolbar_sticky':      'toolbar_sticky',
                 'toolbar_location':    'toolbar_location',
                 'xlabel':              'x_axis_label',
                 'ylabel':              'y_axis_label',
                 'figure.sizing_mode':  'sizing_mode',
                 'figure.width':        'plot_width',
                 'figure.height':       'plot_height',
                 'tools':               'tools'}
        args = self._sizing(*trans.keys(), css = cssarr, translations = trans, **kwa)

        if args.get('tools', _m_none) is _m_none:
            args['tools'] = []
        else:
            args['tools'] = args['tools'].split(',')

        ttips = _m_none
        for css in cssarr if len(cssarr) else iter((self.config, self.css)):
            ttips = css.get('tooltips', default = _m_none)
            if ttips is not _m_none:
                break

        if ttips not in (_m_none, '', None):
            if 'dpxhover' not in args['tools']:
                args['tools'] += [DpxHoverTool(tooltips = ttips)]
            else:
                args['tools'] = [i if i != 'dpxhover' else DpxHoverTool(tooltips = ttips)
                                 for i in args['tools']]
        elif 'dpxhover' in args['tools']:
            args['tools'] = [i if i != 'dpxhover' else DpxHoverTool()
                             for i in args['tools']]

        for name in ('x_range', 'y_range'):
            if args.get(name, _m_none) is Range1d:
                args[name] = Range1d(start = 0., end = 1.)
        return args

    def _keyedlayout(self, ctrl, main, *figs, left = None, bottom = None, right = None):
        return DpxKeyedRow.keyedlayout(ctrl, self, main, *figs,
                                       left   = left,
                                       right  = right,
                                       bottom = bottom,)

    @abstractmethod
    def _addtodoc(self, ctrl, doc):
        "creates the plot structure"

    @abstractmethod
    def _reset(self):
        "initializes the plot for a new file"

    @abstractmethod
    def observe(self, ctrl):
        "sets-up model observers"

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

        plt = ctrl.globals.css.plot
        plt.boundary.overshoot .default  =.001
        plt.tools              .default  ='xpan,box_zoom,reset,save'
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
