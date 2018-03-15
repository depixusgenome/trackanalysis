#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more time series"
from typing             import TypeVar, Generic, List, cast
from bokeh.plotting     import figure, Figure
from bokeh.models       import ColumnDataSource, LinearAxis, DataRange1d

from utils              import initdefaults
from view.plots.base    import PlotAttrs

class TimeSeriesFormat:
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

MODEL  = TypeVar("MODEL")
FORMAT = TypeVar("FORMAT", bound = TimeSeriesFormat)

class TimeSeriesView(Generic[MODEL, FORMAT]):
    "Display time series"
    XLEFT        = "xL"
    XRIGHT       = "xR"
    YLEFT        = "yL"
    YRIGHT       = "yR"
    _format      : FORMAT
    _model       : MODEL
    _leftsource  : ColumnDataSource
    _rightsource : ColumnDataSource
    _fig         : Figure

    def create(self, _):
        "sets the plot up"
        fig = figure(toolbar_sticky   = self._format.toolbar['sticky'],
                     toolbar_location = self._format.toolbar['location'],
                     tools            = self._format.toolbar['items'],
                     plot_width       = self._format.figsize[0],
                     plot_height      = self._format.figsize[1],
                     sizing_mode      = self._format.figsize[2],
                     x_axis_label     = self._format.xlabel,
                     y_axis_label     = self._format.fovnames[self._model.leftvar])

        self._format.leftattr.addto(fig, x = self.XLEFT, y = self.YLEFT,
                                    source = self._leftsource)

        fig.extra_y_ranges = {self.YRIGHT: DataRange1d()}
        fig.add_layout(LinearAxis(y_range_name = self.YRIGHT,
                                  axis_label   = self._format.fovnames[self._model.rightvar]))
        self._format.rightattr.addto(fig, x = self.XRIGHT, y = self.YRIGHT,
                                     source       = self._rightsource,
                                     y_range_name = self.YRIGHT)
        self._fig = fig
        return [fig]

    def observe(self, ctrl):
        "observe events"
        assert self._model.NAME not in ctrl.displays
        ctrl.displays[self._model.NAME] = self._model
        ctrl.observe(self._model.NAME, self.reset)

    def reset(self, _):
        "resets the data"
        names                                            = self._format.fovnames
        self._fig.y_axis_label                           = names[self._model.leftvar]
        self._fig.extra_y_ranges[self.YRIGHT].axis_label = names[self._model.rightvar]

class BeadTimeSeries:
    "Information about the current bead displayed"
    NAME     = "currentbead"
    index    = 0
    leftvar  = "z"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        pass

class BeadTimeSeriesView(TimeSeriesView[BeadTimeSeries, TimeSeriesFormat]):
    "display the current bead"
    def __init__(self):
        super().__init__()
        self._model  = BeadTimeSeries()
        self._format = TimeSeriesFormat()

        lsrc = dict.fromkeys((self.XLEFT,  self.YLEFT),  cast(List[float], []))
        rsrc = dict.fromkeys((self.YRIGHT, self.YRIGHT), cast(List[float], []))
        self._leftsource:  ColumnDataSource = ColumnDataSource(rsrc)
        self._rightsource: ColumnDataSource = ColumnDataSource(lsrc)

    def observe(self, ctrl):
        "observe controller events"
        super().observe(ctrl)
        ctrl.observe(self._onbeaddata)
        ctrl.observe(self._onfovdata)

    def reset(self, ctrl):
        "resets the data"
        super().reset(ctrl)
        self._onbeaddata(ctrl, ctrl.data.beads)
        self._onfovdata (ctrl, ctrl.data.fov)

    def _onfovdata(self, control = None, lines = None, **_):
        time = control.data.fov.dtype.names[0]
        self._rightsource.stream({self.XRIGHT: lines[time],
                                  self.YRIGHT: lines[self._model.rightvar]},
                                 self._format.maxlength)

    def _onbeaddata(self, control = None, lines = None, **_):
        time = control.data.beads.dtype.names[0]
        var  = self._model.leftvar+str(self._model.index)
        self._leftsource.stream({self.XLEFT: lines[time],
                                 self.YLEFT: lines[var]},
                                self._format.maxlength)

class FoVTimeSeries:
    "Information about the current bead displayed"
    NAME     = "currentfov"
    leftvar  = "tsample"
    rightvar = "zmag"
    @initdefaults(frozenset(locals()))
    def ___init__(self, **_):
        pass

class FovTimeSeriesView(TimeSeriesView[FoVTimeSeries, TimeSeriesFormat]):
    "display the current bead"
    XLEFT  = XRIGHT = "x"
    def __init__(self):
        super().__init__()
        src              = dict.fromkeys((self.XLEFT,  self.YRIGHT, self.YLEFT),
                                         cast(List[float], []))
        self._leftsource = self._rightsource = ColumnDataSource(src)
        self._model      = FoVTimeSeries   (leftvar   = "tsample") # type: ignore
        label            = TimeSeriesFormat.fovnames["tsample"]
        self._format     = TimeSeriesFormat(leftlabel = label)     # type: ignore

    def observe(self, ctrl):
        "observe controler events"
        super().observe(ctrl)
        ctrl.observe(self._onfovdata)

    def reset(self, ctrl):
        "resets the data"
        super().reset(ctrl)
        self._onfovdata (ctrl, ctrl.data.fov)

    def _onfovdata(self, control = None, lines = None, **_):
        time = control.data.fov.dtype.names[0]
        self._leftsource.stream({self.XLEFT: lines[time],
                                 self.YLEFT: lines[self._model.leftvar],
                                 self.YRIGHT: lines[self._model.rightvar]},
                                self._format.maxlength)
