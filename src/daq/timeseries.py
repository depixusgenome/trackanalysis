#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more time series"
from   typing           import List, cast

from   bokeh.plotting   import figure, Figure
from   bokeh.models     import ColumnDataSource, LinearAxis, DataRange1d

from   utils            import initdefaults
from   view.threaded    import ThreadedDisplay, DisplayModel
from   view.plots.base  import PlotAttrs

class TimeSeriesTheme:
    "information about the time series displayed"
    name      = "timeseries"
    labels    = {"zmag":    "Magnets (µm)",
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
    xlabel    = "Frames"
    leftlabel = "Bead    (µm)"
    leftattr  = PlotAttrs("lightblue", "circle", 1)
    rightattr = PlotAttrs("red",       "line",   1)
    figsize   = 800, 400, 'fixed'
    maxlength = 5000
    toolbar   = dict(sticky   = False,
                     location = 'right',
                     items    = ['pan,wheel_zoom,box_zoom,save,reset'])
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class TimeSeriesViewMixin:
    "Display time series"
    XLEFT        = "xl"
    XRIGHT       = "xr"
    YLEFT        = "yl"
    YRIGHT       = "yr"
    _leftsource  : ColumnDataSource
    _rightsource : ColumnDataSource
    _fig         : Figure
    def observe(self, ctrl):
        "observe events"
        if self._model.observe(ctrl):
            return

        fcn = lambda **_: self.redisplay(ctrl)
        ctrl.theme.observe  (self._model.theme,   fcn)
        ctrl.display.observe(self._model.display, fcn)

        ctrl.daq.observe('updatenetwork', self.redisplay)

        @ctrl.daq.observe
        def _onlisten(**_): # pylint: disable=unused-variable
            for src in (self._leftsource, self._rightsource):
                src.data = {i: [] for i in src.data}

        for i in ('_onbeadsdata', '_onfovdata'):
            if hasattr(self, i):
                ctrl.daq.observe(getattr(self, i))

        names = ['fov'] + ['beads'] if hasattr(self, '_onbeadsdata') else []

        @ctrl.daq.observe
        def _onupdatenetwork(old = None, **_): # pylint: disable=unused-variable
            if any(i in old for i in names):
                self.redisplay(ctrl)

    def _addtodoc(self, *_):
        "sets the plot up"
        theme = self._model.theme
        fig   = figure(toolbar_sticky   = theme.toolbar['sticky'],
                       toolbar_location = theme.toolbar['location'],
                       tools            = theme.toolbar['items'],
                       plot_width       = theme.figsize[0],
                       plot_height      = theme.figsize[1],
                       sizing_mode      = theme.figsize[2],
                       x_axis_label     = theme.xlabel,
                       y_axis_label     = self._leftlabel())

        theme.leftattr.addto(fig,
                             x      = self.XLEFT,
                             y      = self.YLEFT,
                             source = self._leftsource)

        fig.extra_y_ranges = {self.YRIGHT: DataRange1d()}
        fig.add_layout(LinearAxis(y_range_name = self.YRIGHT,
                                  axis_label   = self._rightlabel()), 'right')
        theme.rightattr.addto(fig,
                              x            = self.XRIGHT,
                              y            = self.YRIGHT,
                              source       = self._rightsource,
                              y_range_name = self.YRIGHT)
        self._fig = fig
        return [fig]

    def _reset(self, _, cache):
        "resets the data"
        names = self._leftlabel(), self._rightlabel()
        for i, j in zip(names, self._fig.yaxis):
            if j.axis_label != i:
                cache[j]['axis_label'] = i

    def _leftlabel(self):
        return self._model.theme.labels[self._model.display.leftvar]

    def _rightlabel(self):
        return self._model.theme.labels[self._model.display.rightvar]

    def redisplay(self, control = None, **_):
        "resets the view"
        self.reset(control)

class BeadTimeSeriesDisplay:
    "Information about the current bead displayed"
    name     = "beadtimeseries"
    index    = 0
    leftvar  = "z0"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class BeadTimeSeriesModel(DisplayModel[BeadTimeSeriesDisplay, TimeSeriesTheme]):
    "model for display the time series"
    def __init__(self, **_):
        super().__init__(name = 'beadtimeseries', **_)

class BeadTimeSeriesView(TimeSeriesViewMixin, ThreadedDisplay[BeadTimeSeriesModel]):
    "display the current bead"
    def __init__(self, **_):
        super().__init__(**_)

        lsrc = dict.fromkeys((self.XLEFT,  self.YLEFT),  cast(List[float], []))
        rsrc = dict.fromkeys((self.XRIGHT, self.YRIGHT), cast(List[float], []))
        self._leftsource  = ColumnDataSource(lsrc)
        self._rightsource = ColumnDataSource(rsrc)

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
        data  = getattr(control, 'daq', control).data

        lines = data.fov.view()[:self._model.theme.maxlength]
        cache[self._rightsource]['data'] = self.__dataright(lines)

        lines = data.beads.view()[:self._model.theme.maxlength]
        cache[self._leftsource]['data']  = self.__dataleft(lines)

    def _onfovdata(self, control = None, lines = None, **_):
        if len(control.config.beads):
            self._rightsource.stream(self.__dataright(lines), self._model.theme.maxlength)

    def _onbeadsdata(self, control = None, lines = None, **_):
        if len(control.config.beads):
            self._leftsource.stream(self.__dataleft(lines), self._model.theme.maxlength)

    def _leftlabel(self):
        return self._model.theme.labels[self._model.display.leftvar[0]]

    def __dataleft(self, data):
        names = data.dtype.names
        if self._model.display.leftvar in names:
            return {self.XLEFT: data[names[0]],
                    self.YLEFT: data[self._model.display.leftvar]}
        return {self.XLEFT: [], self.YLEFT: []}

    def __dataright(self, data):
        names = data.dtype.names
        if len(data) and self._model.rightvar in names:
            return {self.XRIGHT: data[names[0]],
                    self.YRIGHT: data[self._model.display.rightvar]}
        return {self.XRIGHT: [], self.YRIGHT: []}

class FoVTimeSeriesDisplay:
    "Information about the current fov parameter displayed"
    name     = "fovtimeseries"
    leftvar  = "tsample"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class FoVTimeSeriesModel(DisplayModel[FoVTimeSeriesDisplay, TimeSeriesTheme]):
    "model for display the time series"
    def __init__(self, **_):
        super().__init__(name = 'fovtimeseries', **_)

class FoVTimeSeriesView(TimeSeriesViewMixin, ThreadedDisplay[FoVTimeSeriesModel]):
    "display the current fov parameter"
    XLEFT  = XRIGHT = "x"
    def __init__(self, **_):
        src              = dict.fromkeys((self.XLEFT,  self.YRIGHT, self.YLEFT),
                                         cast(List[float], []))
        self._leftsource = self._rightsource = ColumnDataSource(src)
        label            = TimeSeriesTheme.labels["tsample"]
        super().__init__(leftvar   = "tsample", leftlabel = label)

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        lines = control.data.fov[:self._model.theme.maxlength]
        cache[self._leftsource]['data'] = self.__data(lines)

    def _onfovdata(self, lines = None, **_):
        self._leftsource.stream(lines, self._model.theme.maxlength)

    def __data(self, data):
        disp = self._model.display
        if len(disp.leftvar) == 0:
            return {self.XLEFT:  [],
                    self.YLEFT:  [],
                    self.YRIGHT: []}
        return {self.XLEFT:  data[data.dtype.names[0]],
                self.YLEFT:  data[disp.leftvar],
                self.YRIGHT: data[disp.rightvar]}
