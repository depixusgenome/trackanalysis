#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from    typing       import (Tuple, Optional, # pylint: disable=unused-import
                             Iterator, List, Union, cast)
from    enum         import Enum
from    abc          import ABCMeta, abstractmethod
from    contextlib   import contextmanager
from    functools    import wraps
import  inspect

import  numpy        as     np

import  bokeh.palettes
from    bokeh.models            import (Range1d, RadioButtonGroup,
                                        Paragraph, Widget, GlyphRenderer)
from    control                 import Controller
from    control.globalscontrol  import GlobalsAccess
from    ..base                  import BokehView, Action
from    .bokehext               import DpxHoverTool, from_py_func

_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name

class PlotState(Enum):
    "plot state"
    active    = 'active'
    resetting = 'resetting'
    disabled  = 'disabled'
    outofdate = 'outofdate'

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

        colors = palette(count)
        if indexes is not None:
            return [colors[i] for i in indexes]
        else:
            return colors

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
    def reset(self):
        "resets the wiget when a new file is opened"

class GroupWidget(WidgetCreator):
    "Allows creating group widgets"
    INPUT = RadioButtonGroup
    def __init__(self, model) -> None:
        super().__init__(model)
        self._widget  = None # type: ignore

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

    def reset(self):
        "updates the widget"
        self._widget.update(**self._data())

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
        self._ctrl  = getattr(model, '_ctrl', model)

    def clear(self):
        "clears the model's cache"

    def create(self, _):
        "creates the model"

class PlotCreator(GlobalsAccess, metaclass = ABCMeta):
    "Base plotter class"
    _MODEL = PlotModelAccess
    _RESET = frozenset(('track', 'bead'))
    def __init__(self, ctrl:Controller, *_) -> None:
        "sets up this plotter's info"
        ctrl.getGlobal("css.plot").defaults = {'ylabel'             : u'Z (nm)',
                                               'yrightlabel'        : u'Base number',
                                               'xtoplabel'          : u'Time (s)',
                                               'xlabel'             : u'Frames',
                                               'toolbar_location'   : 'right',
                                               'toolbar_sticky'     : False,
                                               'input.width'        : 205,
                                               'figure.width'       : 1200,
                                               'figure.height'      : 800,
                                               'figure.responsive'  : True}

        key = type(self).key()
        for name in 'config', 'project', 'css':
            ctrl.addGlobalMap(name+key)

        super().__init__(ctrl, key)
        self._model                = self._MODEL(ctrl, key)
        self._ctrl                 = ctrl
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

    def action(self, fcn):
        u"decorator which starts a user action but only if state is set to active"
        if tuple(inspect.signature(fcn).parameters) == ('attr', 'old', 'new'):
            @wraps(fcn)
            def _wrap_cb(attr, old, new):
                if self.state is PlotState.active:
                    with Action(self._ctrl):
                        fcn(attr, old, new)
            return _wrap_cb
        elif tuple(inspect.signature(fcn).parameters)[1:] == ('attr', 'old', 'new'):
            @wraps(fcn)
            def _wrap_cb(self, attr, old, new):
                if self.state is PlotState.active:
                    with Action(self._ctrl):
                        fcn(self, attr, old, new)
            return _wrap_cb
        else:
            @wraps(fcn)
            def _wrap_cb(*args, **kwa):
                if self.state is PlotState.active:
                    with Action(self._ctrl):
                        fcn(*args, **kwa)
            return _wrap_cb

    @contextmanager
    def resetting(self):
        "Stops on_change events for a time"
        assert self.state is PlotState.active
        self.state = PlotState.resetting
        yield self
        self.state = PlotState.active # pylint: disable=redefined-variable-type

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

        attrs = dict(bounds        = (vmin, vmax),
                     start         = vmin if curr[0]  is None else curr[0],
                     end           = vmax if curr[1]  is None else curr[1],
                     range_padding = over*100.)
        if not hasattr(rng, 'range_padding'):
            attrs.pop('range_padding')

        return attrs

    def setbounds(self, rng, axis, arr, reinit = True):
        "Sets the range boundaries"
        if reinit and hasattr(rng, 'reinit'):
            rng.update(reinit = not rng.reinit, **self.newbounds(rng, axis, arr))
        else:
            rng.update(**self.newbounds(rng, axis, arr))

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
        self._model.create(doc)
        return self._create(doc)

    def activate(self, val):
        "activates the component: resets can occur"
        old        = self.state
        self.state = PlotState.active if val else PlotState.disabled
        if val and old is PlotState.outofdate:
            with self.resetting():
                self._reset()

    def reset(self, items:dict):
        "Updates the data"
        if not self._needsreset(items):
            return

        if 'track' in items:
            self._model.clear()

        state = self.state
        if   state is PlotState.disabled:
            self.state = PlotState.outofdate

        elif state is PlotState.active:
            with self.resetting():
                self._reset()

    def observe(self):
        "sets-up model observers"
        self.project.root.observe(self.reset)

    def _addcallbacks(self, fig):
        "adds Range callbacks"
        cnf       = self.project
        def _onchangex_cb(attr, old, new):
            if self.state is PlotState.active:
                cnf.update(x = (fig.x_range.start, fig.x_range.end))
        fig.x_range.on_change('start', _onchangex_cb)
        fig.x_range.on_change('end',   _onchangex_cb)

        def _onchangey_cb(attr, old, new):
            if self.state is PlotState.active:
                cnf.update(y = (fig.y_range.start, fig.y_range.end))

        fig.y_range.on_change('start', _onchangey_cb)
        fig.y_range.on_change('end',   _onchangey_cb)

        cnf.defaults = dict(x = (None, None), y = (None, None))

        def _onobserve(items):
            for i in {'x', 'y'} & frozenset(items):
                vals = items[i].value
                getattr(fig, i+'_range').update(start = vals[0], end = vals[1])

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

    @classmethod
    def _needsreset(cls, items) -> bool:
        return not cls._RESET.isdisjoint(items)

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
        ret = self._plotter.create(doc)
        self._plotter.observe()
        return ret,
