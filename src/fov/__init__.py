#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"all FoV view aspects here"
from typing                 import Dict, List, Any # pylint: disable=unused-import
import numpy as np
from bokeh.models           import ColumnDataSource, Range1d, TapTool, HoverTool
from bokeh.plotting         import figure, Figure
from data                   import BEADKEY
from control                import Controller
from control.action         import Action
from control.beadscontrol   import DataSelectionBeadController
from signalfilter           import rawprecision
from view.plots.tasks       import TaskPlotCreator, TaskPlotModelAccess
from view.plots             import PlotAttrs, PlotView
from view.colors            import getcolors, setcolors
from qualitycontrol.view    import QualityControlModelAccess

class FoVPlotCreator(TaskPlotCreator[QualityControlModelAccess]):
    "Plots a default bead and its FoV"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        self.css.defaults = {'beads':   PlotAttrs('color', 'circle', alpha = .5),
                             'text':    PlotAttrs('color',  'text', text_font_style= 'bold'),
                             'image':   PlotAttrs('Greys256', 'image', x = 0, y = 0),
                             'current': PlotAttrs('blue', 'circle', 10),
                             'radius'       : 1.,
                             'figure.width' : 800,
                             'figure.height': 800,
                             'ylabel'       : u'Y (μm)',
                             'xlabel'       : u'X (μm)',
                            }
        setcolors(self,
                  good = 'palegreen', fixed     = 'chocolate',
                  bad  = 'orange',    discarded = 'red')
        self.css.calib.defaults = {'image'  : PlotAttrs('Greys256', 'image'),
                                   'start'  : 1./16.,
                                   'size'   : 6./16}
        self.css.tooltip.default = '<table>@ttips{safe}</table>'
        self.css.tooltip.type.defaults    = {'extent'     : 'Δz',
                                             'hfsigma'    : 'σ[HF]',
                                             'population' : '% good'}
        self.css.tooltip.row.default = ('<tr>'
                                        +'<td>{cycle}</td><td>cycle{plural} with:</td>'
                                        +'<td>{type}</td><td>{message}</td>'
                                        +'</tr>')
        self.css.tooltip.good.default = ('<tr><td><td>'
                                         +'<td>σ[HF] =</td><td>{:.4f}</td>'
                                         +'</tr>')
        self.config.plot.fov.tools.default       = 'pan,box_zoom,tap,save,hover'
        self.config.plot.fov.calib.tools.default = 'pan,box_zoom,save'
        self._fig:         Figure           = None
        self._beadssource: ColumnDataSource = None
        self._cursource:   ColumnDataSource = None
        self._imgsource:   ColumnDataSource = None
        self._calibsource: ColumnDataSource = None
        self._bdctrl                        = DataSelectionBeadController(self._ctrl)
        self.__idfov:      int              = None

    @property
    def __fov(self):
        trk = self._model.track
        return None if trk is None or trk.fov.image is None else trk.fov

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

        self._cursource = ColumnDataSource(**self.__curdata())
        self.css.current.addto(self._fig, x = 'x', y = 'y', source = self._cursource)

        self._beadssource  = ColumnDataSource(**self.__beadsdata())
        args = dict(x = 'x', y = 'y', radius = self.css.radius.get(), source = self._beadssource)
        gl1  = self.css.beads.addto(self._fig, **args)
        gl2  = self.css.text .addto(self._fig, **args, text = 'text')
        self._fig.select(TapTool)[0].renderers = [gl1, gl2]
        self._fig.select(HoverTool)[0].update(renderers = [gl1, gl2],
                                              tooltips  = self.css.tooltip.get())

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

        for rng in self._fig.x_range, self._fig.y_range:
            self.fixreset(rng)
        return self._fig

    __SELECTED: Dict[str, Dict[str, Any]] = {'0d': {'glyph': None, 'indices': []},
                                             '1d': {'indices': []},
                                             '2d': {'indices': []}}
    def _reset(self):
        fov = self.__fov
        if fov is not None and self.__idfov != id(fov):
            self.__idfov = id(fov)
            self.__imagedata()

        self._bkmodels[self._beadssource].update(self.__beadsdata())
        self._bkmodels[self._beadssource].update(selected = self.__SELECTED)
        self._bkmodels[self._cursource].update(self.__curdata())
        self._bkmodels[self._cursource].update(selected = self.__SELECTED)
        self.__calibdata()

    def __calibdata(self):
        fov   = self.__fov
        bead  = self._model.bead
        img   = np.zeros((10, 10))
        dist  = (0, 0, 0, 0)
        if (fov is not None
                and bead in fov.beads
                and fov.beads[bead].image.size):
            bead  = fov.beads[bead]
            img   = bead.image
            pos   = bead.position
            rng   = (max(fov.size()),)*2
            start = self.css.calib.start.get()
            size  = self.css.calib.size.get()
            dist  = [rng[0] * (start+ (0.5 if pos[0] < rng[0]*.5 else 0.)), # type: ignore
                     rng[1] * (start+ (0.5 if pos[1] < rng[1]*.5 else 0.)),
                     rng[0] * size,
                     rng[1] * size]

        self._bkmodels[self._calibsource].update(data = dict(image = [img],
                                                             x     = [dist[0]],
                                                             y     = [dist[1]],
                                                             dw    = [dist[2]],
                                                             dh    = [dist[3]]))

    def __imagedata(self):
        fov = self.__fov
        if fov is None:
            img  = np.zeros((10, 10))
            dist = 1, 1
        else:
            img  = fov.image
            dist = fov.size()

        self._bkmodels[self._imgsource].update(data = dict(image = [img],
                                                           dw    = [dist[0]],
                                                           dh    = [dist[1]]))

        self.setbounds(self._fig.x_range, 'x', [0, max(dist[:2])])
        self.setbounds(self._fig.y_range, 'y', [0, max(dist[:2])])

    def __curdata(self):
        bead = self._model.bead
        fov  = self.__fov
        if fov is None or bead not in fov.beads:
            return dict(data = dict.fromkeys(('x', 'y'), []))

        pos = fov.beads[bead].position
        return dict(data = dict(x = [pos[0]], y = [pos[1]]))

    def __tooltips(self):
        msgs  = self._model.messages()
        trans = self.css.tooltip.type.getitems(...)
        ttips = {} # type: Dict[BEADKEY, List[str]]
        row   = self.css.tooltip.row.get()
        for bead, cyc, tpe, msg  in sorted(zip(msgs['bead'], msgs['cycles'],
                                               msgs['type'], msgs['message']),
                                           key = lambda i: (i[0], -i[1])):
            val = row.format(cycle   = cyc,
                             type    = trans[tpe],
                             message = msg.replace('<', '&lt').replace('>', '&gt'),
                             plural  = 's' if cyc > 1 else '')
            ttips.setdefault(bead, []).append(val)

        row  = self.css.tooltip.good.get()
        trk  = self._model.track
        for bead in self._bdctrl.allbeads:
            if bead not in ttips:
                ttips[bead] = [row.format(rawprecision(trk, bead))]

        return {i: ''.join(j) for i, j in ttips.items()}

    def __beadsdata(self):
        fov = self.__fov
        if fov is None:
            return dict(data = dict.fromkeys(('x', 'y', 'text', 'color', 'ttips'), []))

        hexes = getcolors(self)
        clrs  = hexes['good'], hexes['fixed'], hexes['bad'], hexes['discarded']
        disc  = set(self._bdctrl.discarded)
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
    def ismain(self):
        "Cleaning is set up by default"
        self._ismain(tasks = self.TASKS)
