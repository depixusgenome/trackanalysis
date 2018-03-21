#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more time series"
from typing           import TypeVar, Generic, List, cast

from bokeh.plotting   import figure, Figure
from bokeh.models     import ColumnDataSource, LinearAxis, DataRange1d

from utils            import initdefaults
from utils.inspection import templateattribute
from view.threaded    import ThreadedDisplay, DisplayModel
from view.plots.base  import PlotAttrs

class TimeSeriesTheme:
    "information about the time series displayed"
    fovnames    = {"zmag":    "Magnets (µm)",
                   "x":       "X (µm)",
                   "y":       "Y (µm)",
                   "z":       "Z (µm)",
                   "tsample": "Sample (°C)",
                   "tsink":   "Sink (°C)",
                   "tmagnet": "Magnets (°C)",
                   "vmag":    "Magnets (V)",
                   "led1":    "Led 1 intensity",
                   "led2":    "Led 2 intensity"
                  }
    xlabel      = "Frames"
    leftlabel   = "Bead    (µm)"
    leftattr    = PlotAttrs("lightblue", "circle", 1)
    rightattr   = PlotAttrs("red",       "line",   1)
    figsize     = 800, 400, 'fixed'
    maxlength   = 5000
    toolbar     = dict(sticky = False, location = 'right', items = "")
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        pass

DISPLAY = TypeVar("DISPLAY")
THEME   = TypeVar("THEME", bound = TimeSeriesTheme)

class TimeSeriesModel(Generic[DISPLAY, THEME], DisplayModel):
    "Basic model for time series"
    display: DISPLAY
    theme:   THEME
    def __init__(self, **kwa):
        super().__init__()
        self.display = cast(DISPLAY, templateattribute(self.__class__, 0)(**kwa))
        self.theme   = cast(THEME,   templateattribute(self.__class__, 1)(**kwa))

MODEL  = TypeVar("MODEL", bound = TimeSeriesModel)

class TimeSeriesView(ThreadedDisplay[TimeSeriesModel[DISPLAY, THEME]]):
    "Display time series"
    XLEFT        = "xL"
    XRIGHT       = "xR"
    YLEFT        = "yL"
    YRIGHT       = "yR"
    _leftsource  : ColumnDataSource
    _rightsource : ColumnDataSource
    _fig         : Figure
    def __init__(self, ctrl, **kwa):
        mdl = cast(MODEL, templateattribute(type(self), 0)(**kwa)) # type: ignore
        super().__init__(model = mdl)
        if ctrl:
            self.observe(ctrl)

    def observe(self, ctrl):
        "observe events"
        theme = self._model.theme
        displ = self._model.display
        if displ not in ctrl.display:
            ctrl.theme  .add    (theme)
            ctrl.display.add    (displ)
            ctrl.display.observe(displ, self.redisplay)

    def _addtodoc(self, *_):
        "sets the plot up"
        theme = self._model.theme
        displ = self._model.display
        fig   = figure(toolbar_sticky   = theme.toolbar['sticky'],
                       toolbar_location = theme.toolbar['location'],
                       tools            = theme.toolbar['items'],
                       plot_width       = theme.figsize[0],
                       plot_height      = theme.figsize[1],
                       sizing_mode      = theme.figsize[2],
                       x_axis_label     = theme.xlabel,
                       y_axis_label     = theme.fovnames[displ.leftvar])

        theme.leftattr.addto(fig,
                             x      = self.XLEFT,
                             y      = self.YLEFT,
                             source = self._leftsource)

        fig.extra_y_ranges = {self.YRIGHT: DataRange1d()}
        fig.add_layout(LinearAxis(y_range_name = self.YRIGHT,
                                  axis_label   = theme.fovnames[displ.rightvar]))
        theme.rightattr.addto(fig,
                              x            = self.XRIGHT,
                              y            = self.YRIGHT,
                              source       = self._rightsource,
                              y_range_name = self.YRIGHT)
        self._fig = fig
        return [fig]

    def _reset(self, _, cache):
        "resets the data"
        names = tuple(self._theme.fovnames[getattr(self._model.display, f'{i}var')]
                      for i in ('left', 'right'))
        if self._fig.yaxis.axis_label != names[0]:
            cache[self._fig.yaxis]['axis_label'] = names[0]
        if self._fig.extra_y_ranges[self.YRIGHT].axis_label != names[1]:
            cache[self._fig.extra_y_ranges[self.YRIGHT]]['axis_label'] = names[1]

    def redisplay(self, control = None, **_):
        "resets the view"
        self.reset(control)

class BeadTimeSeries(DisplayModel):
    "Information about the current bead displayed"
    name     = "currentbead"
    index    = 0
    leftvar  = "z"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        super().__init__()

class BeadTimeSeriesView(TimeSeriesView[BeadTimeSeries, TimeSeriesTheme]):
    "display the current bead"
    def __init__(self, ctrl = None):
        super().__init__(ctrl)

        lsrc = dict.fromkeys((self.XLEFT,  self.YLEFT),  cast(List[float], []))
        rsrc = dict.fromkeys((self.YRIGHT, self.YRIGHT), cast(List[float], []))
        self._leftsource:  ColumnDataSource = ColumnDataSource(rsrc)
        self._rightsource: ColumnDataSource = ColumnDataSource(lsrc)

    def observe(self, ctrl):
        "observe controller events"
        super().observe(ctrl)
        ctrl.observe(self._onbeaddata)
        ctrl.observe(self._onfovdata)

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        lines = control.data.fov[:self._theme.maxlength]
        cache[self._rightsource]['data'] = self.__data(lines, 'RIGHT')

        lines = control.data.beads[:self._theme.maxlength]
        cache[self._leftsource]['data']  = self.__data(lines, 'LEFT')

    def _onfovdata(self, lines = None, **_):
        self._rightsource.stream(self.__data(lines, 'RIGHT'), self._theme.maxlength)

    def _onbeaddata(self, lines = None, **_):
        self._leftsource.stream(self.__data(lines, 'LEFT'), self._theme.maxlength)

    def __data(self, data, side):
        var  = 'rightvar' if side == 'RIGHT' else 'leftvar'
        return {getattr(self, 'X'+side): data[data.dtype.names[0]],
                getattr(self, 'Y'+side): data[getattr(self._display, var)]}

class FoVTimeSeries(DisplayModel):
    "Information about the current bead displayed"
    name     = "currentfov"
    leftvar  = "tsample"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        super().__init__(**_)

class FovTimeSeriesView(TimeSeriesView[FoVTimeSeries, TimeSeriesTheme]):
    "display the current bead"
    XLEFT  = XRIGHT = "x"
    def __init__(self, ctrl  = None):
        src              = dict.fromkeys((self.XLEFT,  self.YRIGHT, self.YLEFT),
                                         cast(List[float], []))
        self._leftsource = self._rightsource = ColumnDataSource(src)
        label            = TimeSeriesTheme.fovnames["tsample"]
        super().__init__(ctrl, leftvar  = "tsample", leftlabel = label)

    def observe(self, ctrl):
        "observe controler events"
        super().observe(ctrl)
        ctrl.observe(self._onfovdata)

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        lines = control.data.fov[:self._theme.maxlength]
        cache[self._leftsource]['data'] = self.__data(lines)

    def _onfovdata(self, lines = None, **_):
        self._leftsource.stream(lines, self._theme.maxlength)

    def __data(self, data):
        return {self.XLEFT:  data[data.dtype.names[0]],
                self.YLEFT:  data[self._display.leftvar],
                self.YRIGHT: data[self._display.rightvar]}
