#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all FoV view aspects here"
from typing                 import Dict, List, Optional, Set
import numpy as np
from bokeh.layouts          import column as collayout
from bokeh.models           import (ColumnDataSource, Range1d, TapTool, HoverTool,
                                    Selection)
from bokeh.plotting         import Figure

from control                import Controller
from control.action         import Action
from control.beadscontrol   import DataSelectionBeadController
from cleaning.processor     import DataCleaningErrorMessage
from data                   import BEADKEY
from model.plots            import PlotAttrs, PlotTheme, PlotModel, PlotDisplay
from qualitycontrol.view    import QualityControlModelAccess
from signalfilter           import rawprecision
from utils                  import initdefaults
from view.colors            import tohex
from view.plots.tasks       import (TaskPlotCreator, TaskPlotModelAccess,
                                    TModelType, PlotModelType)
from view.plots.base        import PlotView, CACHE_TYPE

class FoVPlotTheme(PlotTheme):
    "FoV plot theme"
    name        = "fov"
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
    figsize     = PlotTheme.defaultfigsize(160*5, 100*5)
    calibfigsize= PlotTheme.defaultfigsize(256, 192)
    ylabel      = 'Y (μm)'
    xlabel      = 'X (μm)'
    colors      = dict(ok      = 'palegreen', fixed     = 'chocolate',
                       bad     = 'orange',    discarded = 'red',
                       missing = 'magenta')
    thumbnail   = 128
    calibimg    = PlotAttrs('Greys256', 'image', x = 0, y = 0)
    calibsize   = 6./16
    calibtools  = 'pan,box_zoom,save'
    tooltips    = '<table>@ttips{safe}</table>'
    tooltiptype = dict(DataCleaningErrorMessage.NAMES)
    tooltiprow  = ('<tr>'
                   +'<td>{cycle}</td><td>cycle{plural} with:</td>'
                   +'<td>{type}</td><td>{message}</td>'
                   +'</tr>')
    tooltipok   = ('<tr><td><td><td>σ[HF] =</td><td>{:.4f}</td></tr>'
                   '<tr><td><td><td>Δz    =</td><td>{:.2f}</td></tr>'
                  )
    toolbar     = dict(PlotTheme.toolbar)
    toolbar['items'] = 'pan,box_zoom,tap,save,hover'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        super().__init__(**_)

class FoVPlotModel(PlotModel):
    "FoV plot model"
    theme   = FoVPlotTheme()
    display = PlotDisplay(name = "fov")

class BaseFoVPlotCreator(TaskPlotCreator[TModelType, PlotModelType]):
    "Plots a default bead and its FoV"
    _fig:         Figure
    _calibfig:    Figure
    _theme:       FoVPlotTheme
    _beadssource: ColumnDataSource
    _imgsource:   ColumnDataSource
    _calibsource: ColumnDataSource
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self._idfov: Optional[int] = None

    @property
    def _fov(self):
        trk = self._model.track
        return None if trk is None or trk.fov.image is None else trk.fov

    def _addtodoc(self, *_):
        self._fig = self.figure(name    = 'FoV:Fig',
                                x_range = Range1d(0, 1),
                                y_range = Range1d(0, 1))

        self._imgsource   = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         dw    = [1], dh = [1]))
        self.addtofig(self._fig, 'image', **{i:i for i in ('image', 'dw', 'dh')},
                      source = self._imgsource)

        self._calibfig = self.figure(name        = 'FoV:CalibFig',
                                     x_range     = Range1d(0, 1),
                                     y_range     = Range1d(0, 1),
                                     plot_width  = self._theme.calibfigsize[0],
                                     plot_height = self._theme.calibfigsize[1],
                                     sizing_mode = self._theme.calibfigsize[2],
                                     toolbar_location = None,
                                     tools            = [])
        self._calibfig.xaxis.visible     = False
        self._calibfig.yaxis.visible     = False
        self._calibfig.min_border        = 0
        self._calibfig.v_symmetry        = True

        self._calibsource = ColumnDataSource(data = dict(image = [np.zeros((10, 10))],
                                                         dw    = [1], dh = [1]))
        self.addtofig(self._calibfig, 'calibimg', **{i:i for i in ('image', 'dw', 'dh')},
                      source = self._calibsource)


        self._beadssource  = ColumnDataSource(**self._beadsdata())
        args = dict(x = 'x', y = 'y', radius = self._theme.radius, source = self._beadssource)
        gl1  = self.addtofig(self._fig, 'beads', **args)
        gl2  = self.addtofig(self._fig, 'text',  **args, text = 'text')
        self._fig.select(TapTool)[0].renderers = [gl1, gl2]
        self._fig.select(HoverTool)[0].update(renderers = [gl1, gl2],
                                              tooltips  = self._theme.tooltips)

        def _onselect_cb(attr, old, new):
            if len(new) == 0:
                return

            # pylint: disable=unsubscriptable-object
            bead = int(self._beadssource.data['text'][new[0]])
            if bead == self._model.bead:
                return

            with Action(self._ctrl):
                self._ctrl.display.update("tasks", bead = bead)

        # pylint: disable=no-member
        self._beadssource.selected.on_change("indices", _onselect_cb)
        return collayout([self._fig, self._calibfig])

    def _reset(self, cache:CACHE_TYPE):
        fov = self._fov
        if fov is not None and self._idfov != id(fov):
            self._idfov = id(fov)
            self._imagedata(cache)

        cache[self._beadssource].update(self._beadsdata())
        sel  = self._beadssource.selected
        good = [self._model.bead] if self._model.bead is not None else []
        if getattr(sel, 'indices', None) != good:
            if sel is None:
                cache[self._beadssource].update(selected = Selection(indices = good))
            else:
                cache[sel].update(indices = good)

        self._calibdata(cache)

    def _calibdata(self, cache:CACHE_TYPE):
        fov   = self._fov
        ibead = self._model.bead
        img   = np.zeros((10, 10))
        dist  = (0, 0)
        if fov is not None and ibead in fov.beads:
            bead  = fov.beads[ibead]
            img   = (bead.image  if getattr(bead.image, 'size', None) else
                     bead.thumbnail(self._theme.thumbnail, fov))
            rng   = (max(fov.size()),)*2
            size  = self._theme.calibsize
            dist  = rng[0] * size, rng[1] * size

        cache[self._calibsource].update(data = dict(image = [img],
                                                    dw    = [dist[0]],
                                                    dh    = [dist[1]]))
        self.setbounds(cache, self._calibfig, [0, dist[0]], [0, dist[1]])

    def _imagedata(self, cache):
        fov = self._fov
        if fov is None:
            img  = np.zeros((10, 10))
            dist = 1, 1
        else:
            img  = fov.image
            dist = fov.size()

        cache[self._imgsource].update(data = dict(image = [img],
                                                  dw    = [dist[0]],
                                                  dh    = [dist[1]]))

        self.setbounds(cache, self._fig, [0, dist[0]], [0, dist[1]])

    def _beadsdata(self):
        fov = self._fov
        if fov is None:
            return dict(data = dict.fromkeys(('x', 'y', 'text', 'color', 'ttips'), []))

        hexes  = tohex(self._theme.colors)
        clrs   = {i: hexes[i] for i in ('ok', 'fixed', 'bad', 'discarded', 'missing')}
        status = self._status()
        ttips  = self._tooltips()
        items  = fov.beads
        data   = {"x"     : [i.position[0]  for i in items.values()],
                  "y"     : [i.position[1]  for i in items.values()],
                  "text"  : [f'{i}'         for i in items.keys()],
                  "color" : [clrs[next((k for k, l in  status.items() if i in l),
                                       "ok")] for i in items.keys()],
                  "ttips" : [ttips[i] for i in items.keys()]}
        return dict(data = data)

    def _oktooltips(self, ttips):
        row  = self._theme.tooltipok
        trk  = self._model.track
        for bead in DataSelectionBeadController(self._ctrl).allbeads:
            if bead not in ttips:
                ttips[bead] = [row.format(trk.rawprecision(bead),
                                          trk.beadextension(bead))]


        return {i: ''.join(j) for i, j in ttips.items()}

    def _tooltips(self):
        raise NotImplementedError()

    def _status(self) -> Dict[str, Set[int]]:
        raise NotImplementedError()

class FoVPlotCreator(BaseFoVPlotCreator[QualityControlModelAccess, # type: ignore
                                        FoVPlotModel]):
    "Plots a default bead and its FoV"
    def _tooltips(self):
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

        return self._oktooltips(ttips)

    def _status(self) -> Dict[str, Set[int]]:
        return self._model.status()

class FoVPlotView(PlotView[FoVPlotCreator]):
    "FoV plot view"
    PANEL_NAME = 'FoV'
    TASKS      = ('datacleaning',)
    def ismain(self, ctrl):
        "Cleaning is set up by default"
        self._ismain(ctrl, tasks = self.TASKS)
