#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all FoV view aspects here"
from typing           import Dict, Any
import numpy as np
from bokeh.models     import ColumnDataSource, Range1d, TapTool
from bokeh.plotting   import figure, Figure
from control          import Controller
from control.action   import Action
from view.plots.tasks import TaskPlotCreator
from view.plots       import PlotAttrs, PlotView

class FoVPlotCreator(TaskPlotCreator):
    "Plots a default bead and its FoV"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self.css.defaults = {'beads':   PlotAttrs('goldenrod', 'circle', alpha = .5),
                             'text':    PlotAttrs('gold', 'text'),
                             'image':   PlotAttrs('Greys256', 'image', x = 0, y = 0),
                             'current': PlotAttrs('red', 'circle', 16),
                             'radius'       : 1.,
                             'figure.width' : 800,
                             'figure.height': 800,
                             'ylabel'       : u'Y (nm)',
                             'xlabel'       : u'X (nm)',
                            }
        self.css.calib.defaults = {'image'  : PlotAttrs('Greys256', 'image'),
                                   'start'  : 1./16.,
                                   'size'   : 6./16}
        self.config.plot.fov.tools.default       = 'pan,box_zoom,tap,save'
        self.config.plot.fov.calib.tools.default = 'pan,box_zoom,save'
        self._fig:         Figure           = None
        self._beadssource: ColumnDataSource = None
        self._cursource:   ColumnDataSource = None
        self._imgsource:   ColumnDataSource = None
        self._calibsource: ColumnDataSource = None
        self.__fov:        int              = None

    def _create(self, _):
        self._fig = figure(**self._figargs(name    = 'FoV:Fig',
                                           x_range = Range1d(0, 1),
                                           y_range = Range1d(0, 1),
                                           tools   = self.config.plot.fov.tools.get()))

        self._imgsource   = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         dw    = [1], dh = [1]))
        self.css.image.addto(self._fig, **{i:i for i in ('image', 'dw', 'dh')},
                             source = self._imgsource)

        self._calibsource = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         x     = [0], y  = [0],
                                                         dw    = [1], dh = [1]))
        self.css.calib.image.addto(self._fig, **{i:i for i in ('image', 'x', 'y', 'dw', 'dh')},
                                   source = self._calibsource)

        self._beadssource  = ColumnDataSource(**self.__beadsdata())
        args = dict(x = 'x', y = 'y', radius = self.css.radius.get(), source = self._beadssource)
        gl1  = self.css.beads.addto(self._fig, **args)
        gl2  = self.css.text .addto(self._fig, **args, text = 'text')
        self._fig.select(TapTool)[0].renderers = [gl1, gl2]

        def _onselect_cb(attr, old, new):
            inds = new.get('1d', {}).get('indices', [])
            if len(inds) != 1:
                self._beadssource.update(selected = self.__SELECTED)
                return

            bead = int(self._beadssource.data['text'][inds[0]])

            if bead == self._model.bead:
                self._beadssource.update(selected = self.__SELECTED)
                return

            with Action(self._ctrl):
                self.project.root.bead.set(bead)

        self._beadssource.on_change('selected', _onselect_cb)

        self._cursource = ColumnDataSource(**self.__curdata())
        args['source']  = self._cursource
        self.css.current.addto(self._fig, **args)

        for rng in self._fig.x_range, self._fig.y_range:
            self.fixreset(rng)
        return self._fig

    __SELECTED: Dict[str, Dict[str, Any]] = {'0d': {'glyph': None, 'indices': []},
                                             '1d': {'indices': []},
                                             '2d': {'indices': []}}
    def _reset(self):
        track = self._model.track
        if track is not None and self.__fov != id(track.fov):
            self.__fov = id(track.fov)
            self.__imagedata()
            self._bkmodels[self._beadssource].update(self.__beadsdata())

        self._bkmodels[self._beadssource].update(selected = self.__SELECTED)
        self._bkmodels[self._cursource].update(self.__curdata())
        self._bkmodels[self._cursource].update(selected = self.__SELECTED)
        self.__calibdata()

    def __calibdata(self):
        track = self._model.track
        img   = np.zeros((10, 10))
        dist  = (0, 0), (1, 1)
        if track is not None and track.fov.beads[self._model.bead].image.size:
            bead  = track.fov.beads[self._model.bead]
            img   = bead.image
            pos   = bead.position
            rng   = (max(track.fov.size()),)*2
            start = self.css.calib.start.get()
            size  = self.css.calib.size.get()
            dist  = [rng[0] * (start+ (0.5 if pos[0] < rng[0]*.5 else 0.)),
                     rng[1] * (start+ (0.5 if pos[1] < rng[1]*.5 else 0.)),
                     rng[0] * size,
                     rng[1] * size]

        self._bkmodels[self._calibsource].update(data = dict(image = [img],
                                                             x     = [dist[0]],
                                                             y     = [dist[1]],
                                                             dw    = [dist[2]],
                                                             dh    = [dist[3]]))

    def __imagedata(self):
        track = self._model.track
        if track is None:
            img  = np.zeros((10, 10))+256
            dist = 1, 1
        else:
            img  = track.fov.image
            dist = track.fov.size()

        self._bkmodels[self._imgsource].update(data = dict(image = [img],
                                                           dw    = [dist[0]],
                                                           dh    = [dist[1]]))

        self.setbounds(self._fig.x_range, 'x', [0, max(dist[:2])])
        self.setbounds(self._fig.y_range, 'y', [0, max(dist[:2])])

    def __curdata(self):
        bead  = self._model.bead
        track = self._model.track
        if track is None or bead is None:
            return dict(data = dict.fromkeys(('x', 'y'), []))

        pos = track.fov.beads[bead].position
        return dict(data = dict(x = [pos[0]], y = [pos[1]]))

    def __beadsdata(self):
        track = self._model.track
        if track is None:
            return dict(data = dict.fromkeys(('x', 'y', 'text'), []))

        items = track.fov.beads
        data  = dict(x    = [i.position[0] for i in items.values()],
                     y    = [i.position[1] for i in items.values()],
                     text = [f'{i}'        for i in items.keys()])
        return dict(data = data)

class FoVPlotView(PlotView):
    "FoV plot view"
    PLOTTER = FoVPlotCreator
