#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Acces to the camera stream
"""
from   typing                 import Dict, List, Any, Tuple

import numpy                  as     np
import bokeh.core.properties  as     props

import bokeh.layouts          as     layouts
from   bokeh.models           import ColumnDataSource, PointDrawTool
from   bokeh.plotting         import figure, Figure

from   utils                  import initdefaults
from   view.plots.base        import PlotAttrs
from   view.threaded          import DisplayModel, ThreadedDisplay
from   .model                 import DAQBead

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
                          size                 = 10,
                          alpha                = 0.3,
                          selection_color      = 'green',
                          selection_alpha      = .7)
    roi       = PlotAttrs("lightblue", "rect",
                          fill_alpha           = 0.,
                          line_color           = 'lightblue')
    figsize   = 800, 600, 'fixed'
    figborder = 2*28, 28+5
    figstart  = 28, 5
    toolbar   = dict(sticky   = False,
                     location = 'right',
                     items    = 'pan,wheel_zoom,box_zoom,save,reset')

    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
        pass

class CameraDisplay:
    "information about the current bead, ..."
    name        = 'camera'
    currentbead = 0

    @initdefaults(frozenset(locals()) - {'name'})
    def __init__(self, **_):
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
        self._source:   ColumnDataSource = ColumnDataSource({i: [] for i in cols})
        self._ptsource: ColumnDataSource = ColumnDataSource({i: [] for i in ('x', 'y', 'id')})
        if ctrl is not None:
            self.observe(ctrl)

    def _addtodoc(self, ctrl, _):
        "create the bokeh view"
        theme = self._model.theme
        tools = list(theme.toolbar['items'].split(',')) + [PointDrawTool(empty_value = -1)]
        fig   = figure(toolbar_sticky   = theme.toolbar['sticky'],
                       toolbar_location = theme.toolbar['location'],
                       tools            = tools,
                       plot_width       = theme.figsize[0]+theme.figborder[0],
                       plot_height      = theme.figsize[1]+theme.figborder[1],
                       sizing_mode      = theme.figsize[2],
                       x_axis_label     = theme.xlabel,
                       y_axis_label     = theme.ylabel,
                       css_classes      = ['dpxdaqcamera'])

        theme.roi.addto(fig, **{i: i for i in ('x', 'y', 'width', 'height')},
                        source = self._source)

        rend =  theme.position.addto(fig, **{i: i for i in ('x', 'y')}, source = self._ptsource)
        tools[-1].renderers = [rend]

        theme.names.addto(fig, **{i: i for i in ('x', 'y', 'text')}, source = self._source)

        def _onclickedbead_cb(attr, old, new):
            inds = self._ptsource.selected.indices
            ctrl.daq.setcurrentbead(inds[0] if inds else None)
        self._ptsource.on_change('selected', _onclickedbead_cb)

        def _onaddremove_cb(attr, old, new):
            ids   = self._ptsource.data['id']
            dels  = set(range(len(ctrl.daq.config.beads))) - set(ids)
            if -1 in dels:
                dels.discard(-1)
                base  = ctrl.daq.defaultbead.roi
                xvals = self._ptsource.data['x']
                yvals = self._ptsource.data['y']
                added = [{'roi': [xvals[i], yvals[i], base[2], base[3]]}
                         for i, j in enumerate(ids) if j == -1]
            else:
                added = []

            if len(dels):
                ctrl.daq.removebeads(list(self))
            if len(added):
                ctrl.daq.addbeads(added)
        self._ptsource.on_change('data', _onaddremove_cb)

        figsizes    = list(theme.figsize[:2])+list(theme.figstart)
        self._fig = fig
        self._cam = DpxDAQCamera(fig, figsizes, ctrl.daq.config.network.camera,
                                 sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'))
        return [self._cam]

    def _reset(self, ctrl, cache):
        if self._cam.address != ctrl.daq.config.network.camera:
            cache[self._cam]['address'] = ctrl.daq.config.network.camera
        data = self.__data(ctrl)
        cache[self._source].data   = data[0]
        cache[self._ptsource].data = data[1]
        cache[self._ptsource.selected].indices = self.__selected(ctrl)

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
            data                            = self.__data(ctrl)
            self._source.data               = data[0]
            self._ptsource.data             = data[1]
            self._ptsource.selected.indices = self.__selected(ctrl)

        @ctrl.daq.observe
        def _oncurrentbead(bead = None, **_): # pylint: disable=unused-variable
            ctrl.display.update(self._model.display, currentbead = bead)

        @ctrl.daq.observe
        def _onlisten(**_): # pylint: disable=unused-variable
            tmp = dict(self._source.data)
            tmp.clear()
            self._source.data = tmp
            self._cam.start  += 1

        @ctrl.display.observe
        def _oncamera(old = None, **_): # pylint: disable=unused-variable
            if 'currentbead' in old:
                self._ptsource.selected.indices = self.__selected(ctrl)

    @staticmethod
    def __data(ctrl) -> Tuple[Dict[str, Any],Dict[str, Any]]:
        roi  = DAQBead.toarray(ctrl.daq.config.beads)
        data = dict(x     = roi['x'], y      = roi['y'],
                    width = roi['w'], height = roi['h'],
                    text  = [f"{i}" for i in range(len(ctrl.daq.config.beads))])

        ptdata = dict(x = roi['x'], y = roi['y'], id = np.arange(len(ctrl.daq.config.beads)))
        return data, ptdata

    def __selected(self, _) -> List[int]:
        bead = self._model.display.currentbead
        return [] if bead is None else [bead]
