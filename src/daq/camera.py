#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acces to the camera stream
"""
from   typing                 import Dict, Any

import numpy                  as     np
import bokeh.core.properties  as     props

import bokeh.layouts          as     layouts
from   bokeh.models           import ColumnDataSource
from   bokeh.plotting         import figure, Figure

from   utils                  import initdefaults
from   view.plots.base        import PlotAttrs
from   view.threaded          import DisplayModel, ThreadedDisplay
from   view.static            import ROUTE
from   .model                 import DAQBead

class DpxDAQCamera(layouts.Row): # pylint: disable=too-many-ancestors
    """
    Access to the camera stream
    """
    __css__            = ROUTE+"/daqcamera.css"
    __implementation__ = 'camera.coffee'
    address   = props.String("rtsp://192.168.1.56:8554/mystream")
    figwidth  = props.Int(800)
    figheight = props.Int(400)
    start     = props.Int(-1)
    stop      = props.Int(-1)
    def __init__(self, fig, address, **kwa):
        col = layouts.column(children = [fig], css_classes = ['dxpdaqplayer'])
        super().__init__(children    = [col],
                         address     = address,
                         figwidth    = fig.width,
                         figheight   = fig.height,
                         css_classes = ['dpxdaqcontainer'],
                         **kwa)

class CameraTheme:
    "how to display the beads"
    name        = 'camera'
    xlabel      = "x (µm)"
    ylabel      = "y (µm)"
    names       = PlotAttrs("lightblue", "text", x_offset = 5)
    position    = PlotAttrs("lightblue", "circle",
                            size                 = 10,
                            alpha                = 0.3,
                            selection_color      = 'green',
                            selection_alpha      = .7)
    roi         = PlotAttrs("lightblue", "rect",
                            fill_alpha           = 0.,
                            line_color           = 'lightblue')
    figsize     = 800, 400, 'fixed'
    toolbar     = dict(sticky = False, location = 'right', items = "")

    @initdefaults(frozenset(locals()) - {'name'})
    def ___init__(self, **_):
        pass

class CameraDisplay:
    "information about the current bead, ..."
    name        = 'camera'
    currentbead = 0

    @initdefaults(frozenset(locals()) - {'name'})
    def ___init__(self, **_):
        pass

class DAQCameraModel(DisplayModel[CameraDisplay, CameraTheme]):
    "DAQ Camera model"
    pass

class DAQCameraView(ThreadedDisplay[DAQCameraModel]):
    "viewing the camera & beads"
    def __init__(self, ctrl = None, **kwa):
        super().__init__(**kwa)
        self._cam:   DpxDAQCamera     = None
        self._fig:   Figure           = None

        cols = ('x', 'y', 'width', 'height', "text")
        self._source: ColumnDataSource = ColumnDataSource({i: [] for i in cols})
        if ctrl is not None:
            self.observe(ctrl)

    def _addtodoc(self, ctrl, _):
        "create the bokeh view"
        theme = self._model.theme
        fig   = figure(toolbar_sticky   = theme.toolbar['sticky'],
                       toolbar_location = theme.toolbar['location'],
                       tools            = theme.toolbar['items'],
                       plot_width       = theme.figsize[0],
                       plot_height      = theme.figsize[1],
                       sizing_mode      = theme.figsize[2],
                       x_axis_label     = theme.xlabel,
                       y_axis_label     = theme.ylabel,
                       css_classes      = ['dpxdaqcamera'])

        theme.roi.addto(fig, **{i: i for i in ('x', 'y', 'width', 'height')},
                        source = self._source)
        theme.position.addto(fig, **{i: i for i in ('x', 'y')}, source = self._source)
        theme.names.addto(fig, **{i: i for i in ('x', 'y', 'text')}, source = self._source)

        def _onclickedbead_cb(attr, old, new):
            inds = self._source.selected.get('1d', {}).get('indices', [])
            ctrl.daq.setcurrentbead(inds[0] if len(inds) else None)
        self._source.on_change('selected', _onclickedbead_cb)

        self._fig = fig
        self._cam = DpxDAQCamera(fig, address = ctrl.daq.config.network.camera,
                                 sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))
        return [self._cam]

    def _reset(self, ctrl, cache):
        if self._cam.address != ctrl.daq.config.network.camera:
            cache[self._cam]['address'] = ctrl.daq.config.network.camera
        cache[self._source].update(**self.__data(ctrl))

    def observe(self, ctrl):
        """
        observe the controller
        """
        if self._model.observe(ctrl):
            return

        @ctrl.daq.observe
        def _onupdatenetwork(model = None, old = None, **_): # pylint: disable=unused-variable
            if any(i in old for i in ('camera', 'beads')):
                self._cam.update(address = model.camera,
                                 start   = self._cam.start+1)

        @ctrl.daq.observe("addbeads", "removebeads", "updatebeads")
        def _onchangedbeads(**_): # pylint: disable=unused-variable
            self._source.update(**self.__data(ctrl))

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            self.display.model(self._model.display, currentbead = bead)

        @ctrl.daq.observe
        def _onlisten(**_): # pylint: disable=unused-variable
            tmp = dict(self._source.data)
            tmp.clear()
            self._source.data = tmp
            self._cam.start  += 1

        @ctrl.display.observe
        def _oncamera(old = None, **_): # pylint: disable=unused-variable
            if 'currentbead' in old:
                self._source.selected = self.__selected(ctrl)

    def __data(self, ctrl) -> Dict[str, Any]:
        roi  = DAQBead.toarray(ctrl.daq.config.beads)
        data = dict(x     = roi['x'], y      = roi['y'],
                    width = roi['w'], height = roi['h'],
                    text  = np.arange(len(ctrl.daq.config.beads)))
        return {'data': data, 'selected': self.__selected(ctrl)}

    def __selected(self, ctrl) -> Dict[str, Any]:
        bead                 = ctrl.display.model('camera').currentbead
        sel                  = dict(self._source.selected)
        sel['1d']['indices'] = [] if bead is None else [bead]
        return sel
