#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acces to the camera stream
"""
from   functools              import partial
from   typing                 import Dict, Any, Tuple

import numpy                  as     np
import bokeh.core.properties  as     props

import bokeh.layouts          as     layouts
from   bokeh.models           import (ColumnDataSource, PointDrawTool, Range1d,
                                      LinearAxis, CustomJS)
from   bokeh.plotting         import figure, Figure

from   utils                  import initdefaults
from   utils.logconfig        import getLogger
from   view.plots.base        import PlotAttrs
from   view.threaded          import DisplayModel, ThreadedDisplay
from   .model                 import DAQBead
LOGS = getLogger(__name__)

class DpxDAQCamera(layouts.Row): # pylint: disable=too-many-ancestors
    """
    Access to the camera stream
    """
    __implementation__ = 'camera.coffee'
    address   = props.String("rtsp://192.168.1.56:8554/mystream")
    figsizes  = props.List(props.Int, [800, 600, 28, 5])
    start     = props.Int(-1)
    stop      = props.Int(-1)
    def __init__(self, fig, figsizes, address, **kwa):
        col = layouts.column(children = [fig], css_classes = ['dxpdaqplayer'])
        super().__init__(children    = [col],
                         address     = address,
                         figsizes    = figsizes,
                         css_classes = ['dpxdaqcontainer'],
                         **kwa)

class CameraTheme:
    "how to display the beads"
    name      = 'camera'
    xlabel    = "x (µm)"
    ylabel    = "y (µm)"
    names     = PlotAttrs("lightblue", "text", x_offset = 5)
    position  = PlotAttrs("lightblue", "circle",
                          size                    = 10,
                          line_color              = 'lightblue',
                          fill_alpha              = 0.,
                          selection_color         = 'green',
                          selection_alpha         = .7,
                          nonselection_line_color = 'lightblue',
                          nonselection_fill_alpha = .0,
                          nonselection_line_alpha = 1.,
                         )
    roi       = PlotAttrs("lightblue", "rect",
                          fill_alpha           = 0.,
                          line_color           = 'lightblue')
    figsize   = 800, 600, 'fixed'
    figborder = 60, 40, 70, 50
    toolbar   = dict(sticky   = False,
                     location = 'right',
                     items    = 'pan,wheel_zoom,box_zoom,reset')
    decimals  = 3

    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
        pass

class CameraDisplay:
    "information about the current bead, ..."
    name        = 'camera'
    currentbead = None

    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
        pass

class DAQCameraModel(DisplayModel[CameraDisplay, CameraTheme]):
    "DAQ Camera model"
    pass

class DAQCameraView(ThreadedDisplay[DAQCameraModel]):
    "viewing the camera & beads"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._cam:   DpxDAQCamera  = None
        self._fig:   Figure        = None
        self._tool:  PointDrawTool = None

        cols = ('x', 'y', 'width', 'height', "beadid")
        self._source:   ColumnDataSource = ColumnDataSource({i: [] for i in cols})
        self._ptsource: ColumnDataSource = ColumnDataSource({i: [] for i in ('x', 'y', 'beadid')})

    def _addtodoc(self, ctrl, _):
        "create the bokeh view"
        theme = self._model.theme

        fig   = self.__figure(ctrl)
        args  = {i: i for i in ('x', 'y', 'width', 'height')}
        theme.roi.addto(fig, **args, source = self._source)

        args  = {i: i for i in ('x', 'y')}
        theme.names.addto(fig, **args, text = 'beadid', source = self._source)

        rend       = theme.position.addto(fig, **args, source = self._ptsource)
        self._tool = PointDrawTool(renderers = [rend], empty_value = -1)
        fig.add_tools(self._tool)

        self._ptsource.on_change('selected', lambda attr, old, new: self.__onselect(ctrl))
        self._ptsource.on_change('data',     lambda attr, old, new: self.__ondraw(ctrl))

        self._fig = fig
        self._cam = DpxDAQCamera(fig, self.__figsize(ctrl),
                                 ctrl.daq.config.network.camera.address,
                                 sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))

        code = """
               var emb, ref, txt, xvals, yvals;
               emb = document.getElementById("dpxdaqvlc");
               if (emb != null) {
                   xvals = [Math.round(xax.start), Math.round(xax.end)];
                   yvals = [Math.round(yax.start), Math.round(yax.end)];
                   txt = `${xvals[1] - xvals[0]}x${yvals[1] - yvals[0]}+${xvals[0]}+${yvals[0]}`;
                   if ((ref = emb.video) != null) {
                      ref.crop = txt;
                   }
               }
               """
        rng = [fig.extra_x_ranges['xpixel'], fig.extra_y_ranges['ypixel']]
        rng[0].callback = CustomJS(code = code,
                                   args = dict(xax = rng[0], yax = rng[1]))
        rng[1].callback = rng[1].callback

        import bokeh
        if bokeh.__version__ == '0.12.15':
            from bokeh.models import DataTable
            _.add_root(DataTable(editable            = False,
                                 columns             = [],
                                 source              = self._ptsource,
                                 width               = 0,
                                 height              = 0))
        else:
            raise RuntimeError("check whether the previous hack is still needed")
        return [self._cam]

    def observe(self, ctrl):
        """
        observe the controller
        """
        if self._model.observe(ctrl):
            return

        ctrl.daq.observe(partial(self.__onupdatenetwork,  ctrl))
        ctrl.daq.observe(partial(self.__onupdateprotocol, ctrl))
        ctrl.daq.observe("addbeads", "removebeads", "updatebeads",
                         partial(self.__onchangedbeads,   ctrl))
        ctrl.daq.observe(partial(self.__oncurrentbead,    ctrl))
        ctrl.daq.observe(self.__onlisten)
        ctrl.display.observe(self.__oncamera)

    def _reset(self, ctrl, cache):
        if self._cam is None:
            return

        if self._cam.address != ctrl.daq.config.network.camera.address:
            cache[self._cam].update(address = ctrl.daq.config.network.camera.address,
                                    start   = self._cam.start+1)

        manual = ctrl.daq.config.protocol.ismanual()
        if self._tool.drag != manual:
            cache[self._tool].update(drag = manual, add = manual)

        # pylint: disable=unsubscriptable-object
        if self.__figsize(ctrl) != self._cam.figsizes:
            ctrl.theme.update("message",
                              NotImplementedError("Please restart the gui", "error"))

        data = self.__data(ctrl)
        cache[self._source]  .update(data = data[0])
        cache[self._ptsource].update(data = data[1])

        nbeads = len(ctrl.daq.config.beads)
        inds   = [i for i in self._ptsource.selected.indices if i < nbeads]
        bead   = self._model.display.currentbead
        if bead is None and len(inds):
            cache[self._ptsource.selected].update(indices = [])
        elif bead is not None and bead not in inds[:1]:
            inds = [bead] + [i for i in inds if i != bead]
            cache[self._ptsource.selected].update(indices = inds)

    def __data(self, ctrl) -> Tuple[Dict[str, Any],Dict[str, Any]]:
        roi       = DAQBead.toarray(ctrl.daq.config.beads)
        np.round(roi['x'], self._model.theme.decimals, roi['x'])
        np.round(roi['x'], self._model.theme.decimals, roi['x'])
        roi['w'] *= ctrl.daq.config.network.camera.dim[0][0]
        roi['h'] *= ctrl.daq.config.network.camera.dim[1][0]

        data = dict(x      = roi['x'], y      = roi['y'],
                    width  = roi['w'], height = roi['h'],
                    beadid = [f"{i}" for i in range(len(ctrl.daq.config.beads))])

        ptdata = dict(x = roi['x'], y = roi['y'], beadid = np.arange(len(ctrl.daq.config.beads)))
        return data, ptdata

    def __figure(self, ctrl):
        theme   = self._model.theme
        figsize = self.__figsize(ctrl)
        borders = theme.figborder
        bounds  = ctrl.daq.config.network.camera.bounds(False)
        fig     = figure(toolbar_sticky        = theme.toolbar['sticky'],
                         toolbar_location      = theme.toolbar['location'],
                         tools                 = theme.toolbar['items'],
                         plot_width            = figsize[0]+borders[0]+borders[2],
                         plot_height           = figsize[1]+borders[1]+borders[3],
                         background_fill_alpha = 0.,
                         min_border_left       = borders[0],
                         min_border_top        = borders[1],
                         min_border_right      = borders[2],
                         min_border_bottom     = borders[3],
                         sizing_mode           = theme.figsize[2],
                         x_range               = Range1d(bounds[0], bounds[2]),
                         y_range               = Range1d(bounds[1], bounds[3]),
                         x_axis_label          = theme.xlabel,
                         y_axis_label          = theme.ylabel)

        bounds  = ctrl.daq.config.network.camera.bounds(True)
        fig.extra_x_ranges = {'xpixel': Range1d(bounds[0], bounds[2])}
        fig.extra_y_ranges = {'ypixel': Range1d(bounds[1], bounds[3])}
        fig.add_layout(LinearAxis(x_range_name = 'xpixel'), 'above')
        fig.add_layout(LinearAxis(y_range_name = 'ypixel'), 'right')
        return fig

    def __figsize(self, ctrl):
        pix   = list(ctrl.daq.config.network.camera.pixels)
        ratio = pix[1]/pix[0]
        if pix[0] > self._model.theme.figsize[0]:
            pix[1] = int(round(self._model.theme.figsize[0] * ratio))
            pix[0] = self._model.theme.figsize[0]

        if pix[1] > self._model.theme.figsize[1]:
            pix[0] = int(round(self._model.theme.figsize[1] / ratio))
            pix[1] = self._model.theme.figsize[1]

        return pix+list(self._model.theme.figborder[:2])

    def __onselect(self, ctrl):
        src    = self._ptsource
        if -1 in src.data['beadid']:
            return

        bead = src.selected.indices[0] if src.selected.indices else None
        if self._model.display.currentbead != bead:
            ctrl.daq.setcurrentbead(bead)

    def __ondraw(self, ctrl):
        src    = self._ptsource
        ids    = src.data['beadid']
        beads  = ctrl.daq.config.beads
        nbeads = len(beads)

        if -1 in ids[:nbeads]:
            LOGS.warning("wrong ids? %s %s", ids[:nbeads], ids[nbeads:])
        deci   = self._model.theme.decimals
        if len(ids) > nbeads:
            base = ctrl.daq.config.defaultbead.roi
            adds = [{'roi': [round(i, deci), round(j, deci), base[2], base[3]]}
                    for i, j in zip(src.data['x'][nbeads:], src.data['y'][nbeads:])]
            ctrl.daq.addbeads(*adds)

        elif len(ids) < nbeads:
            ctrl.daq.removebeads(*(set(range(nbeads)) - set(ids)))

        else:
            xval  = src.data['x']
            yval  = src.data['y']
            roi   = [(i, [round(xval[i], deci), round(yval[i], deci)]+ beads[i].roi[2:])
                     for i in range(len(xval))]
            maxv  = 10**-deci
            roi   = [(i, j) for i, j in roi
                     if any(abs(x[0]-x[1]) > maxv for x in zip(j[:2], beads[i].roi[:2]))]
            if len(roi):
                ctrl.daq.updatebeads(*((i, {'roi': j}) for i, j in roi))

    def __onupdateprotocol(self, ctrl, **_):
        if self._waitfornextreset() or self._cam is None:
            return
        good = ctrl.daq.config.protocol.ismanual()
        self._tool.update(drag = good, add = good)

    def __onupdatenetwork(self, ctrl, model = None, old = None, **_):
        if 'camera' not in old or self._waitfornextreset() or self._cam is None:
            return

        if model.camera.address != self._cam.address:
            self._cam.update(address = model.camera.address,
                             start   = self._cam.start+1)
        # pylint: disable=unsubscriptable-object
        if self.__figsize(ctrl) != self._cam.figsizes:
            ctrl.theme.update("message",
                              NotImplementedError("Please restart the gui", "error"))

    def __onchangedbeads(self, ctrl, **_):
        if not self._waitfornextreset() or self._cam is None:
            self.reset(ctrl)

    def __oncurrentbead(self, ctrl, bead = None, **_):
        if bead != self._model.display.currentbead:
            ctrl.display.update(self._model.display, currentbead = bead)

    def __onlisten(self, **_):
        if self._cam is not None:
            if len(next(iter(self._source.data.values()))):
                @self._doc.add_next_tick_callback
                def _run():
                    self._source.data = {i: [] for i in self._source.data}
                    self._cam.start  += 1
            else:
                @self._doc.add_next_tick_callback
                def _run2():
                    self._cam.start  += 1

    def __oncamera(self, old = None, **_):
        if 'currentbead' not in old or self._waitfornextreset() or self._cam is None:
            return

        inds = self._ptsource.selected.indices
        bead = self._model.display.currentbead
        if bead is None and len(inds):
            self._ptsource.selected.indices = []
        elif bead is not None and bead not in inds[:1]:
            self._ptsource.selected.indices = [bead] + [i for i in inds if i != bead]
