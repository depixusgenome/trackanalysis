#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"FoV stats view"
from   typing                  import Dict, ClassVar, FrozenSet

import numpy  as np

from   bokeh                   import layouts
from   bokeh.models            import (
    ColumnDataSource, FactorRange, CategoricalAxis, Range1d, LinearAxis, HoverTool
)
from   bokeh.plotting          import figure, Figure

from   view.threaded           import ThreadedDisplay
from   ...model                import FoVStatsPlotModel, BeadsPlotTheme, COLS
from   .._widgets              import MasterWidget
from   .._threader             import BasePlotter, PlotThreader
from   ._xlsx                  import XlsxReport

_XCOLS = frozenset({i.key for i in COLS if i.axis == 'x' and i.raw})
_IDS   = ['trackid', 'bead']

@PlotThreader.setup
class FoVStatsPlot(  # pylint: disable=too-many-instance-attributes
        ThreadedDisplay[FoVStatsPlotModel]
):
    "display the current bead"
    _fig:      Figure
    _topaxis:  CategoricalAxis
    _stats:    ColumnDataSource
    _points:   ColumnDataSource
    _defaults: Dict[str, list]
    _DATAYCOLS: ClassVar[FrozenSet[str]] = frozenset({
        'boxcenter', 'boxheight', 'median', 'bottom', 'top'
    })
    _DATAXCOLS: ClassVar[FrozenSet[str]] = frozenset({'x', 'beadcount'})
    _XAXIS:     ClassVar[type]           = FactorRange

    def __init__(self, widgets = True, **_):
        super().__init__(**_)
        self._plottheme = BeadsPlotTheme("peakcalling.view.beads.plot.theme")
        self._widgets   = () if not widgets else (MasterWidget(),)
        self._defaults  = dict(
            {i: np.array(['']) for i in  _XCOLS | self._DATAXCOLS},
            **{f'{j}': np.array([0.]) for j in self._DATAYCOLS},
        )
        self._defaults['color'] = ["green"]

    _reset = None   # added in _Threader.setup

    def gettheme(self):
        "get the model theme"
        return self._model.theme

    def getdisplay(self):
        "get the model display"
        return self._model.display

    def createplot(self) -> BasePlotter:
        "runs the display"
        from  ._beadstatus import _BeadStatusPlot
        return self._createplot(getattr(_BeadStatusPlot, '_NAME') in self._model.theme.xaxis)

    def swapmodels(self, ctrl):
        "swap with models in the controller"
        super().swapmodels(ctrl)
        self._plottheme = ctrl.theme.swapmodels(self._plottheme)

        for i in self._widgets:
            if hasattr(i, 'swapmodels'):
                i.swapmodels(ctrl)

    def observe(self, ctrl):
        """observe the controller"""
        for i in self._widgets:
            if hasattr(i, 'observe'):
                i.observe(ctrl)

        @ctrl.display.observe(self._model.display)
        def _ontracktags(old, **_):
            if 'tracktag' in old or 'reftrack' in old:
                getattr(self, '_threader').renew(ctrl, 'reset', True)

        theme = frozenset({
            'xinfo', 'yaxisnorm', 'yaxis', 'uselabelcolors',
            'binnedz', 'binnedbp', 'linear', 'defaultcolors',
            *(
                f"{i}{j}"
                for i in ('status', 'beadstatus', 'orientation')
                for j in ('tag', 'color')
            ),
        })

        @ctrl.theme.observe(self._model.theme)
        def _onaxes(old, **_):
            if theme.intersection(old):
                getattr(self, '_threader').renew(ctrl, 'reset', True)

    def getfigure(self) -> Figure:
        "return the figure"
        return self._fig

    def export(self, path) -> bool:
        "return the figure"
        return XlsxReport.export(self, path)

    def _addtodoc(self, ctrl, doc):
        "sets the plot up"
        self._addtodoc_data()
        self._addtodoc_fig()
        if not self._widgets:
            return [self._fig]

        itms      = [i.addtodoc(self, ctrl, doc)[0] for i in self._widgets]
        mode      = {'sizing_mode': ctrl.theme.get('main', 'sizingmode', 'fixed')}
        brds      = ctrl.theme.get("main", "borders", 5)
        width     = sum(i.width  for i in itms) + brds
        height    = max(i.height for i in itms) + brds

        return layouts.column(
            [
                layouts.row(
                    [
                        layouts.widgetbox(i, width = i.width, height = i.height)
                        for i in itms
                    ],
                    width  = width, height = height, **mode
                ),
                self._fig
            ],
            width  = max(width, self._fig.plot_width + brds),
            height = height + self._fig.plot_height,
            **mode,
        )

    def _addtodoc_data(self):
        self._stats  = ColumnDataSource(self._defaults)
        self._points = ColumnDataSource({i: [] for i in  [*_XCOLS, 'x', 'y']})

    def _addtodoc_fig(self):
        "build a figure"
        fig = figure(
            **self._model.theme.figargs,
            x_range = (
                Range1d() if self._XAXIS is not FactorRange else
                FactorRange(factors = self._defaults['x'])
            ),
            y_range = Range1d()
        )
        self._fig = fig

        for i in ('top', 'bottom'):
            self.attrs(self._model.theme.bars).addto(
                self._fig, source = self._stats, y = i
            ).glyph.name = 'bars'

        self.attrs(self._model.theme.points).addto(
            self._fig, source = self._points,
        )
        for i in ('vertices', 'box', 'median'):
            self.attrs(getattr(self._model.theme, i)).addto(
                self._fig, source = self._stats,
            ).glyph.name = i

        if self._XAXIS is FactorRange:
            self._topaxis = CategoricalAxis(
                x_range_name = "beadcount",
                axis_label   = self._model.theme.toplabel[0],
            )
            self._fig.extra_x_ranges = {'beadcount': FactorRange(factors = ['0'])}
        else:
            self._topaxis = LinearAxis(axis_label = self._model.theme.toplabel[0])
        self._fig.add_layout(self._topaxis, 'above')

        hover           = fig.select(HoverTool)[0]
        hover.tooltips  = self._model.theme.tooltipcolumns
        hover.renderers = [next(i for i in self._fig.renderers if i.glyph.name == 'box')]

    def _createplot(self, beadstatus: bool) -> BasePlotter:
        "runs the display"
        from   ._beadstatus            import _BeadStatusPlot
        from   ._hairpin               import _HairpinPlot
        from   ._peak                  import _PeaksPlot

        procs = self._model.tasks.processors
        return (
            _BeadStatusPlot if beadstatus                   else
            _HairpinPlot    if BasePlotter.ishairpin(procs) else
            _PeaksPlot
        )(self, procs)

class FoVStatsLinearPlot(FoVStatsPlot):
    "display the current bead"
    _XAXIS = Range1d
