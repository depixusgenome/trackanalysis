#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing one or more time series"
import re
from   abc              import ABC, abstractmethod
from   functools        import partial
from   contextlib       import contextmanager
from   copy             import deepcopy
from   typing           import Optional

import numpy                  as     np
from   bokeh.plotting         import figure, Figure
from   bokeh.server.callbacks import PeriodicCallback
from   bokeh.models           import ColumnDataSource, LinearAxis, DataRange1d


from   utils            import initdefaults
from   utils.inspection import diffobj
from   view.threaded    import ThreadedDisplay, DisplayModel
from   view.plots.base  import PlotAttrs
from   modaldialog      import dialog
from   .toolbarconfig   import ConfigTool

_ZERO = np.empty(0, dtype = [('_','f4')])

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
    period    = 1. # seconds
    toolbar   = dict(sticky   = False,
                     location = 'above',
                     items    = ['pan,wheel_zoom,box_zoom,save,reset'])
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    _ISBEADS = re.compile(r"^[xyz]\d*$").match
    @classmethod
    def isbeads(cls, val):
        "whether we are looking at beads"
        return cls._ISBEADS(val) is not None

class TimeSeriesViewMixin(ABC):
    "Display time series"
    XLEFT        = "xl"
    XRIGHT       = "xr"
    YLEFT        = "yl"
    YRIGHT       = "yr"
    _leftsource  : ColumnDataSource
    _rightsource : ColumnDataSource
    _fig         : Figure
    _callback    : PeriodicCallback
    _first       : bool
    def observe(self, ctrl):
        "observe events"
        if self._model.observe(ctrl):
            return

        fcn = partial(self._onmodel, ctrl)
        ctrl.theme  .observe(self._model.theme,   fcn)
        ctrl.daq    .observe("listen",            fcn)
        ctrl.display.observe(self._model.display, partial(self._ondisplay, ctrl))
        ctrl.daq    .observe(partial(self._onupdatenetwork, ctrl))

    def _addtodoc(self, ctrl, doc):
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
        tool  = self._configdialog(ctrl, doc) # pylint: disable=assignment-from-none
        if tool:
            fig.add_tools(tool)

        rend = theme.leftattr.addto(fig,
                                    x      = self.XLEFT,
                                    y      = self.YLEFT,
                                    source = self._leftsource)
        fig.y_range.renderers = [rend]

        fig.extra_y_ranges = {self.YRIGHT: DataRange1d()}
        fig.add_layout(LinearAxis(y_range_name = self.YRIGHT,
                                  axis_label   = self._rightlabel()), 'right')
        rend = theme.rightattr.addto(fig,
                                     x            = self.XRIGHT,
                                     y            = self.YRIGHT,
                                     source       = self._rightsource,
                                     y_range_name = self.YRIGHT)
        fig.extra_y_ranges[self.YRIGHT].renderers = [rend]
        self._fig = fig
        return [fig]

    def _reset(self, ctrl, cache):
        "resets the data"
        names = self._leftlabel(), self._rightlabel()
        for i, j in zip(names, self._fig.yaxis):
            if j.axis_label != i:
                cache[j]['axis_label'] = i

        doadd                 = self._doadd(ctrl)
        cback, self._callback = self._callback, (True if doadd else None)
        if cback is True:
            return

        if cback is not None:
            self._doc.remove_periodic_callback(cback)

        fcn         = partial(self._onupdatelines, ctrl)
        period      = self._model.theme.period*1e3
        self._first = True
        if self._callback is True:
            self._callback = self._doc.add_periodic_callback(fcn, period)

    def _xlabel(self):
        return self._model.theme.labels[self._model.display.xvar]

    def _leftlabel(self):
        return self._model.theme.labels[self._model.display.leftvar]

    def _rightlabel(self):
        return self._model.theme.labels[self._model.display.rightvar]

    @abstractmethod
    def _configdialog(self, ctrl, doc) -> Optional[ConfigTool]:
        return None

    def _onmodel(self, ctrl, **_):
        self.reset(ctrl)

    def _onupdatenetwork(self, ctrl, old = None, **_): # pylint: disable=unused-variable
        names = ['fov'] + ['beads'] if hasattr(self, '_onbeadsdata') else []
        if any(i in old for i in names) and not self._waitfornextreset():
            self._onmodel(ctrl)

    def _ondisplay(self, ctrl, **_):
        self.reset(ctrl)

    @abstractmethod
    def _doadd(self, ctrl) -> bool:
        pass

    @abstractmethod
    def _onupdatelines(self, ctrl):
        pass

class BeadTimeSeriesDisplay:
    "Information about the current bead displayed"
    name         = "beadtimeseries"
    xvar         = 'time'
    leftvar      = "z"
    rightvar     = "zmag"
    current: int = None
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

        self._leftsource                 = ColumnDataSource(self._leftdata())
        self._rightsource                = ColumnDataSource(self._rightdata())
        self._leftindex                  = slice(0,0)
        self._rightindex                 = slice(0,0)
        self._callback: PeriodicCallback = None

    def isbeads(self):
        "whether we are looking at beads"
        return self._model.theme.isbeads(self._model.display.leftvar)

    def observe(self, ctrl):
        "observe controller events"
        super().observe(ctrl)

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            mdl = self._model.display
            if self.isbeads():
                name = mdl.leftvar[:1]+('' if bead is None else str(bead))
                ctrl.display.update(mdl, leftvar = name, current = bead)
            else:
                ctrl.display.update(mdl, current = bead)

    def _doadd(self, ctrl):
        "resets the data"
        data  = ctrl.daq.data
        if not data.fovstarted:
            return False

        disp = self._model.display
        fov  = (set(data.fov.view().dtype.names)
                | set(ctrl.daq.config.network.fov.temperatures.names))
        if self.isbeads():
            beads = data.beads.view().dtype.names
            return (ctrl.daq.config.beads and data.beadsstarted
                    and not {disp.xvar, disp.rightvar}.difference(fov)
                    and not {disp.xvar, disp.leftvar }.difference(beads))
        return not {disp.xvar, disp.rightvar, disp.leftvar}.difference(fov)

    def _rightdata(self, lines = _ZERO, var = None):
        disp = self._model.display
        try:
            return {self.XRIGHT: lines[disp.xvar],
                    self.YRIGHT: lines[var if var else disp.rightvar]}
        except ValueError:
            return {self.XRIGHT: [], self.YRIGHT: []}

    def _leftdata(self, lines = _ZERO, var = None):
        disp = self._model.display
        try:
            return {self.XLEFT: lines[disp.xvar],
                    self.YLEFT: lines[var if var else disp.leftvar]}
        except ValueError:
            return {self.XLEFT: [], self.YLEFT: []}

    def _onupdatelines(self, ctrl):
        first, self._first = self._first, False
        temps              = ctrl.daq.config.network.fov.temperatures
        for name, tpe in (('left', 'beads' if self.isbeads() else 'fov'),
                          ('right', 'fov')):
            if first:
                setattr(self, f"_{name}index", slice(0, 0))
            ind, out = getattr(ctrl.daq.data, tpe).since(getattr(self, f"_{name}index"))
            setattr(self, f"_{name}index", ind)

            var = getattr(self._model.display, f'{name}var')
            if tpe == 'fov' and var in temps.names:
                out  = out[temps.indexes(var, out)]
                var  = temps.field[var]

            data     = getattr(self, f"_{name}data")(out, var)
            src      = getattr(self, f"_{name}source")
            if first:
                src.data = data
            else:
                src.stream(data, self._model.theme.maxlength)

        if self.isbeads():
            self._fig.title.text = "Bead %s" % self._model.display.leftvar[1:]
        else:
            self._fig.title.text = ""

    def _leftlabel(self):
        name = self._model.display.leftvar[0 if self.isbeads() else slice(None)]
        return self._model.theme.labels[name]

    def _configdialog(self, ctrl, doc) -> Optional[ConfigTool]:
        transient = deepcopy(self._model.display)

        @contextmanager
        def _context(_):
            yield
            diff = diffobj(transient, self._model.display)
            if not diff:
                return

            with ctrl.action:
                ctrl.display.update(self._model.display, **diff)

        def _body():
            info  = dict(self._model.theme.labels)
            if self._model.display.current is not None:
                for i in 'xyz':
                    info[f'{i}{self._model.display.current}'] = info.pop(i)
            info.pop('time')
            info = {i: j.replace('(','[').replace(')', ']') for i, j in info.items()}
            opts = "%(leftvar|{})c".format('|'.join(f"{i}:{j}" for i, j in info.items()))
            return [['Left y-axis:',  opts]]

        def _onclick_cb(attr, old, new):
            "method to trigger the modal dialog"
            transient.__dict__.update(deepcopy(self._model.display.__dict__))
            return dialog(doc,
                          context = _context,
                          title   = "Configuration",
                          body    = _body(),
                          model   = transient,
                          always  = True)

        tbar = ConfigTool()
        tbar.on_change("configclick", _onclick_cb)
        return tbar

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
        self._leftsource = self._rightsource = ColumnDataSource(self.__data())
        super().__init__(leftvar   = "tsample")
        self._index                      = slice(0,0)
        self._callback: PeriodicCallback = None

    def _doadd(self, ctrl):
        "resets the data"
        disp  = self._model.display
        data  = ctrl.daq.data
        names = data.fov.view().dtype.names
        return (data.fovstarted
                and not {disp.xvar, disp.rightvar, disp.leftvar}.difference(names))

    def _onupdatelines(self, ctrl):
        first, self._first = self._first, False
        if first:
            self._index = slice(0, 0)
        self._index, lines = ctrl.daq.data.fov.since(self._index)
        self._leftsource .stream(self.__data(lines),
                                 len(lines) if first else self._model.theme.maxlength)

    def __data(self, data = _ZERO):
        disp = self._model.display
        try:
            return {self.XLEFT:  data[disp.xvar],
                    self.YLEFT:  data[disp.leftvar],
                    self.YRIGHT: data[disp.rightvar]}
        except ValueError:
            return {self.XLEFT:  [], self.YLEFT:  [], self.YRIGHT: []}

    def _configdialog(self, ctrl, doc) -> Optional[ConfigTool]:
        return None
