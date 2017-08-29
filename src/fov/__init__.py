#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all FOV view aspects here"
from typing           import Dict, Any
import numpy as np
from bokeh.models     import ColumnDataSource, Range1d, TapTool
from bokeh.plotting   import figure, Figure
from control          import Controller
from control.action   import Action
from view.plots.tasks import TaskPlotCreator
from view.plots       import PlotAttrs, PlotView

class FOVPlotCreator(TaskPlotCreator):
    "Plots a default bead and its FOV"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self.css.defaults = {'beads':   PlotAttrs('lightblue', 'circle', alpha = .5),
                             'text':    PlotAttrs('lightblue', 'text'),
                             'image':   PlotAttrs('Greys256', 'image', x = 0, y = 0, alpha = 0.1),
                             'current': PlotAttrs('green', 'circle', 8),
                             'radius'       : 1.,
                             'figure.width' : 450,
                             'figure.height': 450,
                             'ylabel'       : u'Y (nm)',
                             'xlabel'       : u'X (nm)',
                            }
        self.config.plot.tools.default = 'save,tap'
        self._fig:         Figure           = None
        self._beadssource: ColumnDataSource = None
        self._cursource:   ColumnDataSource = None
        self._imgsource:   ColumnDataSource = None
        self.__fov:        int              = None

    def _create(self, _):
        self._fig         = figure(**self._figargs(name    = 'FOV:Fig',
                                                   x_range = Range1d(0, 1),
                                                   y_range = Range1d(0, 1)))

        self._imgsource   = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         dw    = [1], dh = [1]))
        self.css.image.addto(self._fig, **{i:i for i in ('image', 'dw', 'dh')},
                             source = self._imgsource)

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

    def __imagedata(self):
        track = self._model.track
        if track is None:
            img  = np.zeros((10, 10))
            dist = 1, 1
        else:
            img  = track.fov.image
            dist = track.fov.size()

        self._bkmodels[self._imgsource].update(data = dict(image = [img],
                                                           dw    = [dist[0]],
                                                           dh    = [dist[1]]))

        self.setbounds(self._fig.x_range, 'x', [0, dist[0]])
        self.setbounds(self._fig.y_range, 'y', [0, dist[1]])

    def __curdata(self):
        bead  = self._model.bead
        track = self._model.track
        if track is None or bead is None:
            return dict(data = dict.fromkeys(('x', 'y'), []))

        items = track.fov.beads
        return dict(data = dict(x = [items[bead][0]], y = [items[bead][1]]))

    def __beadsdata(self):
        track = self._model.track
        if track is None:
            return dict(data = dict.fromkeys(('x', 'y', 'text'), []))

        items = track.fov.beads
        data  = dict(x = [i for i, _1, _2 in items.values()],
                     y = [i for _1, i, _2 in items.values()],
                     text = [f'{i}' for i in items.keys()])
        return dict(data = data)

class FOVPlotView(PlotView):
    "FOV plot view"
    PLOTTER = FOVPlotCreator
