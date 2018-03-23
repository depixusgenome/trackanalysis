#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more time series"
from   typing           import List, cast
from   functools        import partial

import numpy                as np
from   bokeh.plotting   import figure, Figure
from   bokeh.models     import ColumnDataSource, LinearAxis, DataRange1d

from   utils            import initdefaults
from   view.threaded    import ThreadedDisplay, DisplayModel
from   view.plots.base  import PlotAttrs

class TimeSeriesTheme:
    "information about the time series displayed"
    name        = "timeseries"
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

class TimeSeriesViewMixin:
    "Display time series"
    XLEFT        = "xL"
    XRIGHT       = "xR"
    YLEFT        = "yL"
    YRIGHT       = "yR"
    _leftsource  : ColumnDataSource
    _rightsource : ColumnDataSource
    _fig         : Figure
    def observe(self, ctrl):
        "observe events"
        displ = self._model.display
        if displ in ctrl.display:
            return

        theme = self._model.theme
        ctrl.theme  .add    (theme)
        ctrl.theme.observe  (theme, partial(self.redisplay, ctrl))

        ctrl.display.add    (displ)
        ctrl.display.observe(displ, partial(self.redisplay, ctrl))

        ctrl.daq.observe('updatenetwork', self.redisplay)

        @ctrl.daq.observe
        def _onlisten(**_): # pylint: disable=unused-variable
            for src in (self._leftsource, self._rightsource):
                tmp = dict(self._source.data)
                tmp.clear()
                src.data = tmp

        for i in ('_onbeaddata', '_onfovdata'):
            if hasattr(self, i):
                ctrl.daq.observe(getattr(self, i))

        names = ['fov'] + ['beads'] if hasattr(self, '_onbeaddata') else []

        @ctrl.daq.observe
        def _onupdatenetwork(old = None, **_): # pylint: disable=unused-variable
            if any(i in old for i in names):
                self.redisplay(ctrl)

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

class BeadTimeSeries:
    "Information about the current bead displayed"
    name     = "currentbead"
    index    = 0
    leftvar  = "z0"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        pass

class BeadTimeSeriesView(TimeSeriesViewMixin,
                         ThreadedDisplay[DisplayModel[BeadTimeSeries, TimeSeriesTheme]]):
    "display the current bead"
    def __init__(self, ctrl = None):
        self.__class__.__bases__[1].__init__(self, ctrl, name = 'beadtimeseries')

        lsrc = dict.fromkeys((self.XLEFT,  self.YLEFT),  cast(List[float], []))
        rsrc = dict.fromkeys((self.YRIGHT, self.YRIGHT), cast(List[float], []))
        self._leftsource:  ColumnDataSource = ColumnDataSource(rsrc)
        self._rightsource: ColumnDataSource = ColumnDataSource(lsrc)

        if ctrl:
            self.observe(ctrl)

    def observe(self, ctrl):
        "observe controller events"
        super().observe(ctrl)

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            mdl  = self._model.display
            name = '' if bead is None else str(bead)
            ctrl.display.update(mdl, leftvar = mdl.leftvar[:1]+name)

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        lines = control.data.fov[:self._theme.maxlength]
        cache[self._rightsource]['data'] = self.__dataright(lines)

        lines = control.data.beads[:self._theme.maxlength]
        cache[self._leftsource]['data']  = self.__dataleft(lines)

    def _onfovdata(self, lines = None, **_):
        self._rightsource.stream(self.__dataright(lines), self._theme.maxlength)

    def _onbeaddata(self, lines = None, **_):
        self._leftsource.stream(self.__dataleft(lines), self._theme.maxlength)

    _DEFLEFT  = {TimeSeriesViewMixin.XLEFT:  np.empty(0, dtype = 'f4'),
                 TimeSeriesViewMixin.YLEFT:  np.empty(0, dtype = 'f4')}
    def __dataleft(self, data):
        names = data.dtype.names
        if self._model.leftvar in names:
            return {self.XLEFT: data[names[0]],
                    self.YLEFT: data[self._model.display.leftvar]}
        return self._DEFLEFT

    _DEFRIGHT = {TimeSeriesViewMixin.XRIGHT: np.empty(0, dtype = 'f4'),
                 TimeSeriesViewMixin.YRIGHT: np.empty(0, dtype = 'f4')}
    def __dataright(self, data):
        names = data.dtype.names
        if self._model.rightvar in names:
            return {self.XRIGHT: data[names[0]],
                    self.YRIGHT: data[self._model.display.rightvar]}
        return self._DEFRIGHT

class FoVTimeSeries:
    "Information about the current bead displayed"
    name     = "currentfov"
    leftvar  = "tsample"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        pass

class FoVTimeSeriesView(TimeSeriesViewMixin,
                        ThreadedDisplay[DisplayModel[FoVTimeSeries, TimeSeriesTheme]]):
    "display the current bead"
    XLEFT  = XRIGHT = "x"
    def __init__(self, ctrl  = None):
        src              = dict.fromkeys((self.XLEFT,  self.YRIGHT, self.YLEFT),
                                         cast(List[float], []))
        self._leftsource = self._rightsource = ColumnDataSource(src)
        label            = TimeSeriesTheme.fovnames["tsample"]
        super().__init__(ctrl,
                         name      = 'fovtimeseries',
                         leftvar   = "tsample",
                         leftlabel = label)

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        lines = control.data.fov[:self._theme.maxlength]
        cache[self._leftsource]['data'] = self.__data(lines)

    def _onfovdata(self, lines = None, **_):
        self._leftsource.stream(lines, self._theme.maxlength)

    def __data(self, data):
        disp = self._model.display
        if len(disp.leftvar) == 0:
            return {self.XLEFT:  [],
                    self.YLEFT:  [],
                    self.YRIGHT: []}
        return {self.XLEFT:  data[data.dtype.names[0]],
                self.YLEFT:  data[disp.leftvar],
                self.YRIGHT: data[disp.rightvar]}
