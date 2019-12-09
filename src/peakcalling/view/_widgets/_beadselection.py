#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Widget for selecting a bead"
from abc                   import abstractmethod
from dataclasses           import dataclass, field
from typing                import TypeVar, Generic, ClassVar, FrozenSet
from bokeh.models          import TapTool, CustomJS, ColumnDataSource, Span
import numpy as np
from model.plots           import PlotAttrs
from taskmodel.application import TasksDisplay
from utils.inspection      import templateattribute

Config = TypeVar("Config")

class BeadSelector(Generic[Config]):
    "exports all to csv"
    def __init__(self):
        self._tasks = TasksDisplay()
        self._cnf   = templateattribute(self, 0)()

    def swapmodels(self, ctrl):
        "swap models"
        self._tasks = ctrl.display.swapmodels(self._tasks)
        self._cnf   = ctrl.theme.swapmodels(self._cnf)

    def addtodoc(self, mainviews, ctrl, doc) -> list:
        "creates the widget"
        mainview = next((i for i in mainviews if isinstance(i, self._class())), None)
        if mainview is not None:
            self._add_selector(mainview, ctrl)
            self._add_visual(mainview, ctrl, doc)

            @ctrl.display.observe(self._tasks.name)
            def _onchange(**_):
                mainview.reset(ctrl, fcn = lambda x: self.reset(mainview, x))
        return []

    def _update(self, ctrl, args):
        if args is None or None in args or len(args) != 2:
            return

        root, bead = args
        proc       = ctrl.tasks.processors(root, copy = False)
        if proc is None:
            return

        if root is not self._tasks.roottask:
            ctrl.display.update(self._tasks, taskcache = proc, bead = bead)
        else:
            ctrl.display.update(self._tasks, bead = bead)

    @abstractmethod
    def reset(self, mainview, cache):
        "reset all"

    @staticmethod
    @abstractmethod
    def _class():
        pass

    @abstractmethod
    def _add_selector(self, mainview, ctrl):
        pass

    @abstractmethod
    def _add_visual(self, mainview, ctrl, doc):
        pass

@dataclass
class BeadsPlotSelectorTheme:
    "theme for beads plot"
    color:    str   = 'gray'
    width:    int   = 30
    minwidth: int   = 3
    alpha:    float = 0.3

class BeadsPlotSelector(BeadSelector[BeadsPlotSelectorTheme]):
    "exports all to csv"
    _span: Span

    @staticmethod
    def _class():
        from ..beadsplot import BeadsScatterPlot as view
        return view

    def _add_selector(self, mainview, ctrl):
        def _cb(event):
            self._update(ctrl, mainview.hitpoint(event.x))
        mainview.getfigure().on_event("tap", _cb)

    def _add_visual(self, mainview, ctrl, doc):
        self._span = Span(
            location   = 0.,
            dimension  ='height',
            line_color = self._cnf.color,
            line_width = self._cnf.width,
            line_alpha = 0.
        )
        mainview.getfigure().add_layout(self._span)

    def reset(self, mainview, cache):
        "reset all"
        hpos   = mainview.hitposition(self._tasks.roottask, self._tasks.bead)
        alpha  = getattr(self._span, 'line_alpha')

        fwidth = mainview.getfigure().frame_width
        if fwidth is None:
            fwidth = mainview.getfigure().plot_width - 30  # magic number ...

        if fwidth and fwidth > 0:
            lwidth = max(
                min(self._cnf.width, int(.8 * fwidth/mainview.nfactors)),
                self._cnf.minwidth
            )
        else:
            lwidth = self._cnf.width
        if hpos is None and alpha != 0.:
            cache[self._span].update(line_alpha = 0., line_width = lwidth)
        elif hpos is not None and self._span.location != hpos or alpha != self._cnf.alpha:
            cache[self._span].update(
                line_alpha = self._cnf.alpha, location = hpos, line_width = lwidth
            )


@dataclass
class StatsPlotSelectorTheme:
    "theme for beads plot"
    points: PlotAttrs = field(
        default_factory = lambda: PlotAttrs(
            '#fdae6b', 'x',
            x           = 'x',
            y           = 'y',
            size        = 10,
            line_width  = 2
        )
    )

class StatsPlotSelector(BeadSelector[StatsPlotSelectorTheme]):
    "exports all to csv"
    _source: ColumnDataSource
    _COLS:   ClassVar[FrozenSet[str]] = frozenset(['trackid', 'bead', 'x', 'y'])

    def reset(self, mainview, cache):
        root = self._tasks.roottask
        bead = self._tasks.bead
        good = np.empty(0, dtype = np.bool_)
        data = mainview.getpointsframe()
        if None in (root, bead) or self._COLS.difference(data):
            cache[self._source].update(data = {i: [] for i in 'xy'})
        else:
            good = (data['trackid'] == id(root)) & (data['bead'] == bead)
            cache[self._source].update(data = {i: data[i][good] for i in 'xy'})

    @staticmethod
    def _class():
        from ..statsplot import FoVStatsPlot as view
        return view

    def _add_selector(self, mainview, ctrl):
        fig       = mainview.getfigure()
        rend      = next(i for i in fig.renderers if i.glyph.name == "points")
        fig.tools = fig.tools + [TapTool(renderers = [rend])]

        source = ColumnDataSource(data = {"selection": []})
        rend.data_source.selected.js_on_change(
            "indices",
            CustomJS(
                code = """
                    var inds = cb_obj.indices;
                    if(inds.length == 0) { return; }
                    var sel = {"selection": []};
                    for(var i = 0; i < inds.length; i++)
                    { sel['selection'].push(inds[i]); }
                    mysrc.data = sel;
                    cb_obj.indices = [];
                """,
                args = {'mysrc': source},
            )
        )

        def _cb(attr, old, new):
            if len(new['selection']) == 0:
                return

            ind  = np.random.choice(new['selection'])
            try:
                track = rend.data_source.data['trackid'][ind]
                bead  = int(rend.data_source.data['bead'][ind])
            except (IndexError, ValueError):
                return

            root  = next(
                (j for j in (next(i) for i in ctrl.tasks.tasklist(...)) if id(j) == track),
                None
            )
            self._update(ctrl, (root, bead))

        source.on_change("data", _cb)

    def _add_visual(self, mainview, ctrl, doc):
        self._source = ColumnDataSource(data = {'x': [], 'y': []})
        mainview.attrs(self._cnf.points).addto(mainview.getfigure(), source = self._source)
