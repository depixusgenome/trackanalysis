#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acces to the camera stream
"""
from   typing                 import Dict, Any, Tuple

import numpy                  as     np
import bokeh.core.properties  as     props

import bokeh.layouts          as     layouts
from   bokeh.models           import (ColumnDataSource, PointDrawTool, Range1d, LinearAxis)
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
    figborder = 52+61, 25+44
    figstart  = 52, 25
    toolbar   = dict(sticky   = False,
                     location = 'right',
                     items    = 'pan,wheel_zoom,box_zoom,save,reset')
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
        self._cam:   DpxDAQCamera     = None
        self._fig:   Figure           = None

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

        rend = theme.position.addto(fig, **args, source = self._ptsource)
        tool = PointDrawTool(renderers = [rend], empty_value = -1)
        fig.add_tools(tool)

        self._ptsource.on_change('selected', lambda attr, old, new: self.__onselect(ctrl))
        self._ptsource.on_change('data',     lambda attr, old, new: self.__ondraw(ctrl))

        self._fig = fig
        self._cam = DpxDAQCamera(fig, self.__figsize(ctrl),
                                 ctrl.daq.config.network.camera.address,
                                 sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))
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

        @ctrl.daq.observe
        def _onupdatenetwork(model = None, old = None, **_): # pylint: disable=unused-variable
            if 'camera' not in old or self._waitfornextreset() or self._cam is None:
                return

            if model.camera.address != self._cam.address:
                self._cam.update(address = model.camera.address,
                                 start   = self._cam.start+1)
            # pylint: disable=unsubscriptable-object
            if self.__figsize(ctrl) != self._cam.figsizes:
                ctrl.theme.update("message",
                                  NotImplementedError("Please restart the gui", "error"))

        @ctrl.daq.observe("addbeads", "removebeads", "updatebeads")
        def _onchangedbeads(**_): # pylint: disable=unused-variable
            if not self._waitfornextreset() or self._cam is None:
                self.reset(ctrl)

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            if bead != self._model.display.currentbead:
                ctrl.display.update(self._model.display, currentbead = bead)

        @ctrl.daq.observe
        def _onlisten(**_): # pylint: disable=unused-variable
            if self._cam is None:
                return

            tmp = dict(self._source.data)
            tmp.clear()
            self._source.data = tmp
            self._cam.start  += 1

        @ctrl.display.observe
        def _oncamera(old = None, **_): # pylint: disable=unused-variable
            if 'currentbead' not in old or self._waitfornextreset() or self._cam is None:
                return

            inds = self._ptsource.selected.indices[:1]
            bead = self._model.display.currentbead
            if bead is None and len(inds):
                self._ptsource.selected.indices = []
            elif bead is not None and bead not in inds[:1]:
                self._ptsource.selected.indices = [bead] + [i for i in inds if i != bead]

    def _reset(self, ctrl, cache):
        if self._cam is None:
            return

        if self._cam.address != ctrl.daq.config.network.camera.address:
            cache[self._cam].update(address = ctrl.daq.config.network.camera.address,
                                    start   = self._cam.start+1)

        # pylint: disable=unsubscriptable-object
        if self.__figsize(ctrl) != self._cam.figsizes:
            ctrl.theme.update("message",
                              NotImplementedError("Please restart the gui", "error"))

        data = self.__data(ctrl)
        cache[self._source]  .update(data = data[0])
        cache[self._ptsource].update(data = data[1])

        nbeads = len(ctrl.daq.config.beads)
        inds   = [i for i in self._ptsource.selected.indices[:1] if i < nbeads]
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
        bounds  = ctrl.daq.config.network.camera.bounds(False)
        fig     = figure(toolbar_sticky   = theme.toolbar['sticky'],
                         toolbar_location = theme.toolbar['location'],
                         tools            = theme.toolbar['items'],
                         plot_width       = figsize[0]+theme.figborder[0],
                         plot_height      = figsize[1]+theme.figborder[1],
                         sizing_mode      = theme.figsize[2],
                         x_range          = Range1d(bounds[0], bounds[2]),
                         y_range          = Range1d(bounds[1], bounds[3]),
                         x_axis_label     = theme.xlabel,
                         y_axis_label     = theme.ylabel)

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

        return pix+list(self._model.theme.figstart)

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

        assert -1 not in ids[:nbeads]
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
            roi   = [(i, j) for i, j in roi if beads[i].roi[:2] != j[:2]]
            if len(roi):
                ctrl.daq.updatebeads(*((i, {'roi': j}) for i, j in roi))
