#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more time series"
from   functools        import partial
from   typing           import List, cast

import numpy            as     np
from   bokeh.plotting   import figure, Figure
from   bokeh.models     import ColumnDataSource, LinearAxis, DataRange1d


from   utils            import initdefaults
from   view.threaded    import ThreadedDisplay, DisplayModel
from   view.plots.base  import PlotAttrs

class TimeSeriesTheme:
    "information about the time series displayed"
    name      = "timeseries"
    labels    = {"zmag":    "Magnets (µm)",
                 "time":    "Frames",
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
    leftattr  = PlotAttrs("lightblue", "circle", size=5)
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

        fcn = partial(self._onmodel, ctrl)
        ctrl.theme.observe  (self._model.theme,   fcn)
        ctrl.display.observe(self._model.display, fcn)
        ctrl.daq.observe(self._onlisten)
        ctrl.daq.observe(partial(self._onupdatenetwork, ctrl))

    def _addtodoc(self, *_):
        "sets the plot up"
        theme = self._model.theme
        fig   = figure(toolbar_sticky   = theme.toolbar['sticky'],
                       toolbar_location = theme.toolbar['location'],
                       tools            = theme.toolbar['items'],
                       plot_width       = theme.figsize[0],
                       plot_height      = theme.figsize[1],
                       sizing_mode      = theme.figsize[2],
                       x_axis_label     = self._xlabel(),
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

    def _xlabel(self):
        return self._model.theme.labels[self._model.display.xvar]

    def _leftlabel(self):
        return self._model.theme.labels[self._model.display.leftvar]

    def _rightlabel(self):
        return self._model.theme.labels[self._model.display.rightvar]

    def _onmodel(self, ctrl, **_):
        self.reset(ctrl)

    def _onlisten(self, **_): # pylint: disable=unused-variable
        if any(len(next(iter(src.data.values())))
               for src in (self._leftsource, self._rightsource)):
            @self._doc.add_next_tick_callback
            def _run():
                for src in (self._leftsource, self._rightsource):
                    src.data = {i: [] for i in src.data}

    def _onupdatenetwork(self, ctrl, old = None, **_): # pylint: disable=unused-variable
        names = ['fov'] + ['beads'] if hasattr(self, '_onbeadsdata') else []
        if any(i in old for i in names):
            self._onmodel(ctrl)

class BeadTimeSeriesDisplay:
    "Information about the current bead displayed"
    name     = "beadtimeseries"
    index    = 0
    xvar     = 'time'
    leftvar  = "z"
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

        self._leftsource  = ColumnDataSource(self._leftdata())
        self._rightsource = ColumnDataSource(self._rightdata())

    def observe(self, ctrl):
        "observe controller events"
        super().observe(ctrl)

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            mdl  = self._model.display
            name = mdl.leftvar[:1]+('' if bead is None else str(bead))
            ctrl.display.update(mdl, leftvar = name)

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        data   = getattr(control, 'daq', control).data
        length = self._model.theme.maxlength
        good   = lambda x: all(i is not self._ZERO for i in x.values())
        right  = self._rightdata(data.fov  .view()[:length])
        left   = self._leftdata (data.beads.view()[:length])
        if len(control.daq.config.beads) and good(right) and good(left):
            def _obs():
                control.daq.observe(self._onbeadsdata)
                control.daq.observe(self._onfovdata)
            cache[self._rightsource]['data'] = right
            cache[self._leftsource]['data']  = left
            cache[self]                      = _obs
        else:
            control.daq.remove(self._onbeadsdata)
            control.daq.remove(self._onfovdata)
            cache[self._rightsource]['data'] = self._leftdata()
            cache[self._leftsource]['data']  = self._rightdata()

    _ZERO = np.empty(0, dtype = [('_','f4')])
    def _rightdata(self, lines = _ZERO):
        disp = self._model.display
        try:
            return {self.XRIGHT: lines[disp.xvar], self.YRIGHT: lines[disp.rightvar]}
        except ValueError:
            return {self.XRIGHT: [], self.YRIGHT: []}

    def _leftdata(self, lines = _ZERO):
        disp = self._model.display
        try:
            return {self.XLEFT: lines[disp.xvar], self.YLEFT: lines[disp.leftvar]}
        except ValueError:
            return {self.XLEFT: [], self.YLEFT: []}

    def _onfovdata(self, lines = None, **_):
        disp = self._model.display
        try:
            data = {self.XRIGHT: lines[disp.xvar], self.YRIGHT: lines[disp.rightvar]}
        except ValueError:
            return
        fcn  = lambda: self._rightsource.stream(data, self._model.theme.maxlength)
        self._doc.add_next_tick_callback(fcn)

    def _onbeadsdata(self, lines = None, **_):
        disp = self._model.display
        try:
            data = {self.XLEFT: lines[disp.xvar], self.YLEFT: lines[disp.leftvar]}
        except ValueError:
            return
        fcn  = lambda: self._leftsource.stream(data, self._model.theme.maxlength)
        self._doc.add_next_tick_callback(fcn)

    def _leftlabel(self):
        return self._model.theme.labels[self._model.display.leftvar[0]]

class FoVTimeSeriesDisplay:
    "Information about the current fov parameter displayed"
    name     = "fovtimeseries"
    xvar     = 'time'
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
        super().__init__(leftvar   = "tsample")

    def _reset(self, control, cache):
        "resets the data"
        super()._reset(control, cache)
        lines = control.data.fov[:self._model.theme.maxlength]
        cache[self._leftsource]['data'] = self.__data(lines)

    def _onfovdata(self, lines = None, **_):
        fcn  = lambda: self._leftsource.stream(lines, self._model.theme.maxlength)
        self._doc.add_next_tick_callback(fcn)

    def __data(self, data):
        disp = self._model.display
        try:
            return {self.XLEFT:  data[disp.xvar],
                    self.YLEFT:  data[disp.leftvar],
                    self.YRIGHT: data[disp.rightvar]}
        except ValueError:
            return {self.XLEFT:  [], self.YLEFT:  [], self.YRIGHT: []}
