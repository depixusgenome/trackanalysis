#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acces to the camera stream
"""
from   typing                 import Dict, Any
from   bokeh.models           import Model, ColumnDataSource
from   bokeh.plotting         import figure, Figure
import bokeh.core.properties  as     props

from   utils                  import initdefaults
from   view.plots.base        import PlotAttrs
from   view.threaded          import DisplayModel, ThreadedDisplay
from   view.static            import ROUTE

class DpxDAQCamera(Model):
    """
    Access to the camera stream
    """
    __css__            = ROUTE+"/daqcamera.css"
    __implementation__ = 'camera.coffee'
    address  = props.String("rtsp://192.168.1.56:8554/mystream")
    figclass = props.String("dpxdaqcamera")

class CameraTheme:
    "how to display the beads"
    name        = 'camera'
    xlabel      = "x (µm)"
    ylabel      = "y (µm)"
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

class DAQCameraView(ThreadedDisplay[DisplayModel[CameraDisplay, CameraTheme]]):
    "viewing the camera & beads"
    def __init__(self, ctrl = None, **kwa):
        super().__init__(**kwa)
        self._cam:   DpxDAQCamera     = None
        self._fig:   Figure           = None

        cols = ('x', 'y', 'width', 'height')
        self._source: ColumnDataSource = ColumnDataSource({i: [] for i in cols})
        if ctrl is not None:
            self.observe(ctrl)

    def _addtodoc(self, ctrl, doc):
        "create the bokeh view"
        self._cam = DpxDAQCamera(address = ctrl.daq.config.network.camera)
        doc.add_root(self._cam)

        theme = self._model.theme
        fig   = figure(toolbar_sticky   = theme.toolbar['sticky'],
                       toolbar_location = theme.toolbar['location'],
                       tools            = theme.toolbar['items'],
                       plot_width       = theme.figsize[0],
                       plot_height      = theme.figsize[1],
                       sizing_mode      = theme.figsize[2],
                       x_axis_label     = theme.xlabel,
                       y_axis_label     = theme.ylabel)

        theme.roi.addto(fig, **{i: i for i in ('x', 'y', 'width', 'height')},
                        source = self._source)
        theme.position.addto(fig, **{i: i for i in ('x', 'y')}, source = self._source)

        def _onclickedbead_cb(attr, old, new):
            inds = self._source.selected.get('1d', {}).get('indices', [])
            ctrl.daq.setcurrentbead(inds[0] if len(inds) else None)
        self._source.on_change('selected', _onclickedbead_cb)

    def _reset(self, ctrl, cache):
        if self._cam.address != ctrl.daq.config.network.camera:
            cache[self._cam]['address'] = ctrl.daq.config.network.camera
        cache[self._source].update(**self.__data(ctrl))

    def observe(self, ctrl):
        """
        observe the controller
        """
        if self._model.theme in self.theme:
            return
        self.theme.add(self._model.theme)
        self.display.add(self._model.display)

        @ctrl.daq.observe
        def _onupdatenetwork(model = None, old = None, **_): # pylint: disable=unused-variable
            if any(i in old for i in ('camera', 'beads')):
                self._cam.address = model.camera

        @ctrl.daq.observe("addbeads", "removebeads", "updatebeads")
        def _onchangedbeads(**_): # pylint: disable=unused-variable
            self._source.update(**self.__data(ctrl))

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            self.display.model(self._model.display, currentbead = bead)

        @ctrl.display.observe
        def _oncamera(old = None, **_): # pylint: disable=unused-variable
            if 'currentbead' in old:
                self._source.selected = self.__selected(ctrl)

    def __data(self, ctrl) -> Dict[str, Any]:
        roi  = lambda i: [j.roi[i] for j in ctrl.daq.config.beads]
        cols = ('x', 'y', 'width', 'height')
        return {'data': {j: roi(i) for i, j in enumerate(cols)},
                'selected': self.__selected(ctrl)}

    def __selected(self, ctrl) -> Dict[str, Any]:
        bead                 = ctrl.display.model('camera').currentbead
        sel                  = dict(self._source.selected)
        sel['1d']['indices'] = [] if bead is None else [bead]
        return sel