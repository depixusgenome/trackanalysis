#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all FoV view aspects here"
from typing                 import Dict, List, Any # pylint: disable=unused-import
import numpy as np
from bokeh.models           import (ColumnDataSource, Range1d, TapTool, HoverTool,
                                    Selection)
from bokeh.plotting         import Figure

from control                import Controller
from control.action         import Action
from control.beadscontrol   import DataSelectionBeadController
from data                   import BEADKEY
from model.plots            import PlotAttrs, PlotTheme, PlotModel
from qualitycontrol.view    import QualityControlModelAccess
from signalfilter           import rawprecision
from utils                  import initdefaults
from view.colors            import tohex
from view.plots.tasks       import TaskPlotCreator, TaskPlotModelAccess
from view.plots.base        import PlotView, CACHE_TYPE

class FoVPlotTheme(PlotTheme):
    "FoV plot theme"
    name        = "fovplot"
    beads       = PlotAttrs('color', 'circle',
                            alpha                   = .7,
                            nonselection_alpha      = .7,
                            selection_alpha         = .7,
                            nonselection_color      = 'color',
                            selection_fill_color    = 'color')
    text        = PlotAttrs('color',  'text',
                            text_font_style         = 'bold',
                            nonselection_alpha      = 1.,
                            nonselection_text_color = "color",
                            selection_alpha         = 1.,
                            selection_text_color    = 'blue')
    image       = PlotAttrs('Greys256', 'image', x = 0, y = 0)
    radius      = 1.
    figsize     = 800, 800, 'fixed'
    ylabel      = 'Y (μm)'
    xlabel      = 'X (μm)'
    colors      = dict(good = 'palegreen', fixed     = 'chocolate',
                       bad  = 'orange',    discarded = 'red')
    thumbnail   = 128
    calibimg    = PlotAttrs('Greys256', 'image')
    calibstart  = 1./16.
    calibsize   = 6./16
    calibtools  = 'pan,box_zoom,save'
    tooltips    = '<table>@ttips{safe}</table>'
    tooltiptype = {'extent'     : 'Δz',
                   'pingpong'   : 'Σ|dz|',
                   'hfsigma'    : 'σ[HF]',
                   'population' : '% good',
                   'saturation' : 'non-closing'}
    tooltiprow  = ('<tr>'
                   +'<td>{cycle}</td><td>cycle{plural} with:</td>'
                   +'<td>{type}</td><td>{message}</td>'
                   +'</tr>')
    tooltipgood = ('<tr><td><td>'
                   +'<td>σ[HF] =</td><td>{:.4f}</td>'
                   +'</tr>')
    toolbar     = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,tap,save,hover'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class FoVPlotModel(PlotModel):
    "FoV plot model"
    theme = FoVPlotTheme()

class FoVPlotCreator(TaskPlotCreator[QualityControlModelAccess, FoVPlotModel]):
    "Plots a default bead and its FoV"
    _fig:         Figure
    _theme:       FoVPlotTheme
    _beadssource: ColumnDataSource
    _imgsource:   ColumnDataSource
    _calibsource: ColumnDataSource
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self.__idfov: int = None

    @property
    def __fov(self):
        trk = self._model.track
        return None if trk is None or trk.fov.image is None else trk.fov

    def _addtodoc(self, *_):
        self._fig = self._theme.figure(name    = 'FoV:Fig',
                                       x_range = Range1d(0, 1),
                                       y_range = Range1d(0, 1))

        self._imgsource   = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         dw    = [1], dh = [1]))
        self._theme.image.addto(self._fig, **{i:i for i in ('image', 'dw', 'dh')},
                                source = self._imgsource)

        self._calibsource = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         x     = [0], y  = [0],
                                                         dw    = [1], dh = [1]))
        self._theme.calibimg.addto(self._fig, **{i:i for i in ('image', 'x', 'y', 'dw', 'dh')},
                                   source = self._calibsource)

        self._beadssource  = ColumnDataSource(**self.__beadsdata())
        args = dict(x = 'x', y = 'y', radius = self._theme.radius, source = self._beadssource)
        gl1  = self._theme.beads.addto(self._fig, **args)
        gl2  = self._theme.text .addto(self._fig, **args, text = 'text')
        self._fig.select(TapTool)[0].renderers = [gl1, gl2]
        self._fig.select(HoverTool)[0].update(renderers = [gl1, gl2],
                                              tooltips  = self._theme.tooltips)

        def _onselect_cb(attr, old, new):
            inds = new.indices
            if len(inds) == 0:
                return

            # pylint: disable=unsubscriptable-object
            bead = int(self._beadssource.data['text'][inds[0]])
            if bead == self._model.bead:
                return

            with Action(self._ctrl):
                self._ctrl.display.update("tasks", bead = bead)

        self._beadssource.on_change('selected', _onselect_cb)

        for rng in self._fig.x_range, self._fig.y_range:
            self.fixreset(rng)
        return self._fig

    def _reset(self, cache:CACHE_TYPE):
        fov = self.__fov
        if fov is not None and self.__idfov != id(fov):
            self.__idfov = id(fov)
            self.__imagedata(cache)

        cache[self._beadssource].update(self.__beadsdata())
        sel  = self._beadssource.selected
        good = [self._model.bead] if self._model.bead is not None else []
        if getattr(sel, 'indices', None) != good:
            if sel is None:
                cache[self._beadssource].update(selected = Selection(indices = good))
            else:
                cache[sel].update(indices = good)

        self.__calibdata(cache)

    def __calibdata(self, cache:CACHE_TYPE):
        fov   = self.__fov
        ibead = self._model.bead
        img   = np.zeros((10, 10))
        dist  = (0, 0, 0, 0)
        if fov is not None and ibead in fov.beads:
            bead  = fov.beads[ibead]
            img   = (bead.image if bead.image.size else
                     bead.thumbnail(self._theme.thumbnail, fov))

            pos   = bead.position
            rng   = (max(fov.size()),)*2
            start = self._theme.calibstart
            size  = self._theme.calibsize
            dist  = [rng[0] * (start+ (0.5 if pos[0] < rng[0]*.5 else 0.)), # type: ignore
                     rng[1] * (start+ (0.5 if pos[1] < rng[1]*.5 else 0.)),
                     rng[0] * size,
                     rng[1] * size]

        cache[self._calibsource].update(data = dict(image = [img],
                                                    x     = [dist[0]],
                                                    y     = [dist[1]],
                                                    dw    = [dist[2]],
                                                    dh    = [dist[3]]))

    def __imagedata(self, cache):
        fov = self.__fov
        if fov is None:
            img  = np.zeros((10, 10))
            dist = 1, 1
        else:
            img  = fov.image
            dist = fov.size()

        cache[self._imgsource].update(data = dict(image = [img],
                                                  dw    = [dist[0]],
                                                  dh    = [dist[1]]))

        self.setbounds(cache, self._fig.x_range, 'x', [0, max(dist[:2])])
        self.setbounds(cache, self._fig.y_range, 'y', [0, max(dist[:2])])

    def __tooltips(self):
        msgs                            = self._model.messages()
        ttips: Dict[BEADKEY, List[str]] = {}
        row                             = self._theme.tooltiprow
        for bead, cyc, tpe, msg  in sorted(zip(msgs['bead'], msgs['cycles'],
                                               msgs['type'], msgs['message']),
                                           key = lambda i: (i[0], -i[1])):
            val = row.format(cycle   = cyc,
                             type    = self._theme.tooltiptype[tpe],
                             message = msg.replace('<', '&lt').replace('>', '&gt'),
                             plural  = 's' if cyc > 1 else '')
            ttips.setdefault(bead, []).append(val)

        row  = self._theme.tooltipgood
        trk  = self._model.track
        for bead in DataSelectionBeadController(self._ctrl).allbeads:
            if bead not in ttips:
                ttips[bead] = [row.format(rawprecision(trk, bead))]

        return {i: ''.join(j) for i, j in ttips.items()}

    def __beadsdata(self):
        fov = self.__fov
        if fov is None:
            return dict(data = dict.fromkeys(('x', 'y', 'text', 'color', 'ttips'), []))

        hexes = tohex(self._theme.colors)
        clrs  = hexes['good'], hexes['fixed'], hexes['bad'], hexes['discarded']
        disc  = set(DataSelectionBeadController(self._ctrl).discarded)
        fixed = self._model.fixedbeads() - disc
        bad   = self._model.badbeads() - disc - fixed
        ttips = self.__tooltips()

        items = fov.beads
        data  = dict(x     = [i.position[0]  for i in items.values()],
                     y     = [i.position[1]  for i in items.values()],
                     text  = [f'{i}'         for i in items.keys()],
                     color = [clrs[3 if i in disc  else
                                   2 if i in bad   else
                                   1 if i in fixed else
                                   0] for i in items.keys()],
                     ttips = [ttips[i] for i in items.keys()])
        return dict(data = data)

class FoVPlotView(PlotView[FoVPlotCreator]):
    "FoV plot view"
    TASKS = ('datacleaning',)
    def ismain(self, ctrl):
        "Cleaning is set up by default"
        self._ismain(ctrl, tasks = self.TASKS)
