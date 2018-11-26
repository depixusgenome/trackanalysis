#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cycles plot view"
import  bokeh.core.properties as     props
from    bokeh.models          import (ColumnDataSource, CustomJS, TapTool,
                                      HoverTool, Renderer)

from    sequences.view        import SequenceHoverMixin
from    view.plots            import DpxHoverTool, PlotAttrsView, themed

class DpxHoverModel(HoverTool,  # pylint: disable=too-many-instance-attributes,too-many-ancestors
                    SequenceHoverMixin):
    "controls keypress actions"
    maxcount  = props.Int(3)
    framerate = props.Float(1.)
    shape     = props.Tuple(props.Int, props.Int, default = (0, 0))
    cycle     = props.Int(-1)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    updating  = props.String('')
    rawrend   = props.Instance(Renderer)
    impl      = SequenceHoverMixin.impl
    __implementation__ = impl('DpxHoverModel',
                              ('shape: [p.Array, [2,1]],'
                               'cycle: [p.Int, -1],'
                               'rawrend: [p.Instance, null],'),
                              __file__)

    @staticmethod
    def _createrawdata(data, shape):
        return dict(t = data['t'][:shape[1]], z = data['z'][:shape[1]])

    @staticmethod
    def __settooltips(fig, theme):
        tooltips = theme.tooltips
        hover    = fig.select(DpxHoverTool)

        if tooltips is None or len(tooltips) == 0:
            if len(hover):
                hover[0].tooltips = None

        elif len(hover):
            name = theme.raw.glyph
            rend = [i for i in fig.renderers
                    if hasattr(i, 'glyph') and type(i.glyph).__name__.lower() == name][0]
            hover[0].tooltips  = tooltips
            hover[0].renderers = [rend]
            rend.selection_glyph        = None
            rend.nonselection_glyph     = None
            rend.glyph.radius_dimension = 'x'
            rend.glyph.radius           = theme.radius

    def __settap(self, mdl, fig, source, theme):
        tap  = fig.select(TapTool)
        if tap is not None and len(tap):
            src   = ColumnDataSource(self._createrawdata(source.data, self.shape))
            sel   = themed(mdl, theme.selection)
            glyph = PlotAttrsView(sel).addto(fig,  x = 't', y = 'z', source = src)
            args  = dict(hvr    = self,
                         hvrsrc = src,
                         rawsrc = source,
                         glyph  = glyph)
            code  = "hvr.launch_hover(rawsrc, hvrsrc, glyph)"
            self.rawrend = glyph
            source.callback = CustomJS(code = code, args = args)

    def createraw(self, mdl, fig, source, shape, theme): # pylint: disable=too-many-arguments
        "creates the hover tool"
        self.shape  = tuple(shape)
        self.__settooltips(fig, theme)
        self.__settap(mdl, fig, source, theme)

    def slaveaxes(self, fig, src):
        "slaves a histogram's axes to its y-axis"
        fig.y_range.callback = CustomJS(code = "hvr.on_change_hist_bounds(fig, src)",
                                        args = dict(hvr = self, fig = fig, src = src))

    def resetraw(self, fig, rdata, shape, resets):
        "updates the tooltips for a new file"
        hover = fig.select(DpxHoverTool)
        if len(hover) == 0:
            return

        resets[self]['shape'] = shape
        if self.rawrend is not None:
            resets[self.rawrend]['visible']          = False
            resets[self.rawrend.data_source]['data'] = self._createrawdata(rdata, shape)
