#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing              import (Tuple, Optional,       # pylint: disable=unused-import
                                    Iterator, Sequence, List, Union, Dict, Any, cast)
from    collections         import OrderedDict
from    enum                import Enum
from    abc                 import ABCMeta, abstractmethod
from    contextlib          import contextmanager
from    functools           import wraps

import  numpy        as     np

import  bokeh.palettes
from    bokeh.document          import Document     # pylint: disable=unused-import
from    bokeh.models            import (Range1d,    # pylint: disable=unused-import
                                        RadioButtonGroup, Model,
                                        Paragraph, Widget, GlyphRenderer)

from    control                 import Controller
from    control.globalscontrol  import GlobalsAccess
from    ..base                  import BokehView, threadmethod, spawn
from    .bokehext               import DpxHoverTool, from_py_func

_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name

class PlotState(Enum):
    "plot state"
    active       = 'active'
    abouttoreset = 'abouttoreset'
    resetting    = 'resetting'
    disabled     = 'disabled'
    outofdate    = 'outofdate'

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
                 color                  = 'blue',
                 glyph                  = 'line',
                 size                   = 1,
                 palette: Optional[str] = None,
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

    def addto(self, fig, **kwa) -> GlyphRenderer:
        "adds itself to plot: defines color, size and glyph to use"
        args  = dict(self.__dict__)
        args.pop('glyph')
        args.pop('palette')
        args.update(kwa)

        if self.glyph == 'circle' and 'radius' in args:
            args.pop('size')

        if self.glyph in ('line', 'quad'):
            args['line_width'] = args.pop('size')

        return getattr(fig, self.glyph)(**args)

class WidgetCreator(GlobalsAccess, metaclass = ABCMeta):
    "Base class for creating a widget"
    def __init__(self, model:GlobalsAccess) -> None:
        super().__init__(model)
        self._model = model
        self._ctrl  = getattr(model, '_ctrl')

    def observe(self):
        "sets-up config observers"

    @abstractmethod
    def create(self, action) -> List[Widget]:
        "Creates the widget"

    @abstractmethod
    def reset(self, resets):
        "resets the wiget when a new file is opened"

class GroupWidget(WidgetCreator):
    "Allows creating group widgets"
    INPUT = RadioButtonGroup
    def __init__(self, model) -> None:
        super().__init__(model)
        self._widget  = None # type: Optional[RadioButtonGroup]

    def create(self, action) -> List[Widget]:
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

class PlotModelAccess(GlobalsAccess):
    "Default plot model"
    def __init__(self, model:Union[Controller, 'PlotModelAccess'], key = None) -> None:
        super().__init__(model, key)
        self._ctrl   = getattr(model, '_ctrl', model)

    def clear(self):
        "clears the model's cache"

    def create(self, _):
        "creates the model"

    @staticmethod
    def reset() -> bool:
        "resets the model"
        return False

class PlotCreator(GlobalsAccess, metaclass = ABCMeta):
    "Base plotter class"
    _MODEL = PlotModelAccess
    _RESET = frozenset(('bead',))
    _CLEAR = frozenset(('track',))
    class _OrderedDict(OrderedDict):
        def __missing__(self, key):
            self[key] = value = OrderedDict()
            return value

    def __init__(self, ctrl:Controller, *_) -> None:
        "sets up this plotter's info"
        ctrl.getGlobal("css.plot").defaults = {'ylabel'             : u'Z (nm)',
                                               'yrightlabel'        : u'Base number',
                                               'xtoplabel'          : u'Time (s)',
                                               'xlabel'             : u'Frames',
                                               'toolbar_location'   : 'right',
                                               'toolbar_sticky'     : False,
                                               'input.width'        : 205,
                                               'figure.width'       : 800,
                                               'figure.height'      : 500,
                                               'figure.responsive'  : True}

        key = type(self).key()
        for name in 'config', 'project', 'css':
            ctrl.addGlobalMap(name+key)

        super().__init__(ctrl, key)
        self._model                = self._MODEL(ctrl, key)
        self._ctrl                 = ctrl
        self._bkmodels             = self._OrderedDict() # type: Dict[Model,Dict[str,Any]]
        self._doc                  = None                # type: Optional[Document]
        self.project.state.default = PlotState.active

    state = cast(PlotState,
                 property(lambda self:    self.project.state.get(),
                          lambda self, i: self.project.state.set(PlotState(i))))

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

    @contextmanager
    def resetting(self):
        "Stops on_change events for a time"
        self._bkmodels.clear()
        old, self.state = self.state, PlotState.resetting
        try:
            yield self
            for i, j in self._bkmodels.items():
                i.update(**j)
        finally:
            self._bkmodels.clear()
            self.state = old

    @staticmethod
    def fixreset(arng):
        "Corrects the reset bug in bokeh"
        assert isinstance(arng, Range1d)
        @from_py_func
        def _onchangebounds(cb_obj = None):
            # pylint: disable=protected-access,no-member
            if cb_obj.bounds is not None:
                cb_obj._initial_start = cb_obj.bounds[0]
                cb_obj._initial_end   = cb_obj.bounds[1]

        arng.callback = _onchangebounds

    def close(self):
        "Removes the controller"
        del self._ctrl
        del self._doc

    def newbounds(self, rng, axis, arr) -> dict:
        "Sets the range boundaries"
        over  = self.config.boundary.overshoot.get()

        if isinstance(arr, np.ndarray):
            vmin  = np.nanmin(arr)
            vmax  = np.nanmax(arr)
        else:
            vmin  = min(arr)
            vmax  = max(arr)
        delta = (vmax-vmin)*over*.5
        vmin -= delta
        vmax += delta

        if axis is None:
            curr  = None, None # type: Tuple[Optional[float], Optional[float]]
        else:
            curr  = self.project[axis].get(default = (vmin, vmax))

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

        vmin  = min(arr)
        vmax  = max(arr)
        delta = (vmax-vmin)*self.config.boundary.overshoot.get()
        vmin -= delta
        vmax += delta
        return vmin, vmax

    def create(self, doc):
        "returns the figure"
        self._doc = doc
        self._model.create(doc)
        with self.resetting():
            return self._create(doc)

    def activate(self, val):
        "activates the component: resets can occur"
        old        = self.state
        self.state = PlotState.active if val else PlotState.disabled
        if val and (old is PlotState.outofdate):
            self.__doreset()

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
            self.__doreset()

        elif state is PlotState.abouttoreset:
            with self.resetting():
                self._model.reset()

    def observe(self):
        "sets-up model observers"
        self.project.root.observe(self.reset)

    if False: # pylint: disable=using-constant-test
        # use this for single-thread debugging
        def __doreset(self):
            with self.resetting():
                self._model.reset()
                self._reset()
            self._ctrl.handle('rendered', args = {'plot': self})
    else:
        def __doreset(self):
            with self.resetting():
                self._bkmodels.clear()
                self._model.reset()

            old, self.state = self.state, PlotState.abouttoreset
            async def _reset_and_render():
                def _reset():
                    self.state = PlotState.resetting
                    with BokehView.computation.type(self._ctrl, calls = self.__doreset):
                        try:
                            self._reset()
                            return tuple(self._bkmodels.items())
                        finally:
                            self._bkmodels.clear()
                            self.state = old

                ret = await threadmethod(_reset)

                def _render():
                    if ret is not None:
                        with BokehView.computation.type(self._ctrl, calls = self.__doreset):
                            with self.resetting():
                                self._bkmodels.update(ret)
                    self._ctrl.handle('rendered', args = {'plot': self})

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
                    vals = axis.start, axis.end
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
        args.pop('sizing_mode' if args.get('responsive', False) else 'responsive',
                 None)
        return args

    def _figargs(self, *cssarr, **kwa) -> dict:
        trans = {'toolbar_sticky':      'toolbar_sticky',
                 'toolbar_location':    'toolbar_location',
                 'xlabel':              'x_axis_label',
                 'ylabel':              'y_axis_label',
                 'figure.sizing_mode':  'sizing_mode',
                 'figure.responsive':   'responsive',
                 'figure.width':        'plot_width',
                 'figure.height':       'plot_height',
                 'tools':               'tools'}
        args = self._sizing(*trans.keys(), css = cssarr, translations = trans, **kwa)

        if args.get('tools', _m_none) is _m_none:
            args['tools'] = []
        else:
            args['tools'] = args['tools'].split(',')

        ttips = _m_none
        for css in cssarr:
            ttips = css.get('tooltips', default = _m_none)
            if ttips is not _m_none:
                break

        if ttips not in (_m_none, '', None) and 'dpxhover' not in args['tools']:
            args['tools'] += [DpxHoverTool()]
        elif 'dpxhover' in args['tools']:
            args['tools'] = [i if i != 'dpxhover' else DpxHoverTool()
                             for i in args['tools']]
        for name in ('x_range', 'y_range'):
            if args.get(name, _m_none) is Range1d:
                args[name] = Range1d(start = 0., end = 0.)
        return args

    @abstractmethod
    def _create(self, doc):
        "creates the plot structure"

    @abstractmethod
    def _reset(self):
        "initializes the plot for a new file"

class PlotView(BokehView):
    "plot view"
    PLOTTER = None # type: Optional[type]
    def __init__(self, **kwa):
        super().__init__(**kwa)

        def _gesture(meta):
            return {'rate'    : .2,
                    'activate': meta[:-1],
                    'x.low'   : meta+'ArrowLeft',
                    'x.high'  : meta+'ArrowRight',
                    'y.low'   : meta+'ArrowDown',
                    'y.high'  : meta+'ArrowUp'}

        plt = self._ctrl.getGlobal('config.plot')
        plt.tools              .default  ='xpan,box_zoom,reset,save'
        plt.boundary.overshoot .default  =.001
        plt.keypress.reset     .default  ='Shift- '
        plt.keypress.pan       .defaults = _gesture('Alt-')
        plt.keypress.zoom      .defaults = _gesture('Shift-')

        self._plotter = self.PLOTTER(self._ctrl) # pylint: disable=not-callable

    @property
    def plotter(self):
        "returns the plot creator"
        return self._plotter

    def _ismain(self, tasks = None, ioopen = None, iosave = None):
        "Set-up things if this view is the main one"
        self._plotter.ismain(self._keys)

        cnf = self._ctrl.getGlobal('config').tasks
        if tasks is not None:
            cnf.default = tasks

        for name, vals in (('open', ioopen), ('save', iosave)):
            if vals is None:
                continue

            old = cnf.io[name].get()
            new = []
            for i in vals:
                if isinstance(i, (str, int)):
                    new.append(old[i] if isinstance(i, int) else i)
                elif isinstance(i, slice) or i is Ellipsis:
                    new.extend(old if i is Ellipsis else old[i])
            cnf.io[name].default = new

    def close(self):
        "remove controller"
        super().close()
        self._plotter.close()
        self._plotter = None

    def activate(self, val):
        "activates the component: resets can occur"
        self._plotter.activate(val)

    def getroots(self, doc):
        "adds items to doc"
        super().getroots(doc)
        ret = self._plotter.create(doc)
        self._plotter.observe()
        return ret,
