#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The basic architecture"
from enum   import Enum
from typing import Tuple, Optional, Iterator, List, Any, Dict, cast, TYPE_CHECKING

from utils  import initdefaults
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from bokeh.models   import GlyphRenderer
    from bokeh.plotting import Figure

RANGE_TYPE  = Tuple[Optional[float], Optional[float]]

class PlotState(Enum):
    "plot state"
    active       = 'active'
    abouttoreset = 'abouttoreset'
    resetting    = 'resetting'
    disabled     = 'disabled'
    outofdate    = 'outofdate'

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
        import  bokeh.palettes
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
        import  bokeh.palettes
        palette = getattr(bokeh.palettes, self.palette, None)
        if palette is None:
            return [self.color]*count
        elif isinstance(palette, dict):
            colors: List[str] = max(palette.values(), key = len)
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

    def addto(self, fig, **kwa) -> 'GlyphRenderer':
        "adds itself to plot: defines color, size and glyph to use"
        args = dict(self.__dict__)
        args.pop('glyph')
        args.update(kwa)
        getattr(self, '_'+self.glyph, self._default)(args)
        return getattr(fig, self.glyph)(**args)

class PlotTheme:
    """
    Default plot theme
    """
    name          = ''
    ylabel        = 'Z (μm)'
    yrightlabel   = 'Base number'
    xtoplabel     = 'Time (s)'
    xlabel        = 'Frames'
    figsize       = 800, 600, 'fixed'
    overshoot     =.001
    toolbar       = dict(sticky   = False,
                         location = 'above',
                         items    = 'xpan,wheel_zoom,box_zoom,save')
    tooltips: Any = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

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

        from view.plots.bokehext import DpxHoverTool
        if tips:
            hvr = DpxHoverTool(tooltips = tips)
            if 'dpxhover' not in tools:
                tools.append(hvr)
            else:
                tools = [i if i != 'dpxhover' else hvr for i in tools]

        elif 'dpxhover' in tools:
            tools = [i if i != 'dpxhover' else DpxHoverTool() for i in tools]
        args['tools'] = tools

        from bokeh.models import Range1d
        for name in ('x_range', 'y_range'):
            if args.get(name, None) is Range1d:
                args[name] = Range1d(start = 0., end = 1.)
        return args

    def figure(self, **kwa) -> 'Figure':
        "creates a figure"
        from bokeh.plotting import figure
        return figure(**self.figargs(**kwa))

class PlotDisplay:
    """
    Default plot display
    """
    name                = ""
    state               = PlotState.active
    xbounds: RANGE_TYPE = (None, None)
    ybounds: RANGE_TYPE = (None, None)
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        pass

    def addcallbacks(self, ctrl, fig):
        "adds Range callbacks"
        updating = [False]
        def _get(attr):
            axis = getattr(fig, attr+'_range')

            def _on_cb(attr, old, new):
                if self.state is PlotState.active:
                    vals = cast(Tuple[Optional[float],...], (axis.start, axis.end))
                    if axis.bounds is not None:
                        rng  = 1e-3*(axis.bounds[1]-axis.bounds[0])
                        vals = tuple(None if abs(i-j) < rng else j
                                     for i, j in zip(axis.bounds, vals))
                    updating[0] = True
                    ctrl.display.update(self, **{attr+'bounds': vals})
                    updating[0] = False

            axis.on_change('start', _on_cb)
            axis.on_change('end',   _on_cb)

        _get('x')
        _get('y')

        def _onobserve(old = None, **_):
            if updating[0]:
                return
            for i in {'xbounds', 'ybounds'} & frozenset(old):
                rng  = getattr(fig, i[0]+'_range')
                vals = getattr(self, i)
                bnds = rng.bounds
                rng.update(start = bnds[0] if vals[0] is None else vals[0],
                           end   = bnds[1] if vals[1] is None else vals[1])
        ctrl.display.observe(self, _onobserve)
        return fig

class PlotModel:
    """
    base plot model
    """
    theme       = PlotTheme()
    display     = PlotDisplay()
    config: Any = None
    def __init__(self, key, **kwa):
        self.theme   = type(self.__class__.theme)(name = key, **kwa)
        self.display = type(self.__class__.display)(name = key, **kwa)
        if self.__class__.config:
            self.config  = type(self.__class__.config)(name = key+"config", **kwa)

    def observe(self, ctrl, noerase = True):
        "sets-up model observers"
        self.theme   = ctrl.theme  .add(self.theme, noerase)
        self.display = ctrl.display.add(self.display, noerase)
        if self.config:
            self.config = ctrl.theme  .add(self.config, noerase)

    @classmethod
    def create(cls, ctrl, key, **kwa):
        "creates the model and registers it"
        self = cls(key, **kwa)
        self.observe(ctrl, True)
        return self
