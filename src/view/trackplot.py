#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from bokeh.plotting import figure
from bokeh.models   import LinearAxis, Range1d
from .              import FlexxView, ui

def plotbead(ctrl):
    u"sets-up the figure"
    task = ctrl.getGlobal("current.track", default = None)
    if task is None:
        return figure(tools = [])

    key   = 'plot.bead.'
    items = next(iter(ctrl.run(task, task)))
    bead  = ctrl.getGlobal("current.bead", default = None)
    if bead is None:
        bead = next(iter(items.keys()))

    def _add(beadname, beadvalues, **kwargs):
        glyph = ctrl.getConfig(key+beadname+".glyph")
        yvals = items[beadvalues]
        args  = dict(x     = items['t'],
                     y     = yvals,
                     color = ctrl.getConfig(key+beadname+".color"),
                     size  = ctrl.getConfig(key+beadname+".size"),
                     **kwargs
                    )
        if glyph == 'line':
            args['line_width'] = args.pop('size')

        if 'y_range_name' in kwargs:
            vmin = yvals.min()
            vmin = vmin * (.95  if vmin > 0. else 1./.95)
            vmax = yvals.max()
            vmax = vmax * (1./.95 if vmax > 0. else .95)
            inte = vmax-vmin
            fig.extra_y_ranges = {beadname: Range1d(start = vmin, end = vmax,
                                                    min_interval = inte,
                                                    max_interval = inte)}

            fig.add_layout(LinearAxis(y_range_name=beadname), 'right')

        getattr(fig, glyph)(**args)

    fig = figure(tools = ctrl.getConfig(key+"tools"),
                 x_axis_label = 'Time',
                 y_axis_label = 'z',
                )
    _add("z", bead)
    _add("zmag", "zmag", y_range_name = 'zmag')
    return fig

class TrackPlot(FlexxView):
    u"Track plot view"
    def init(self):
        self._plot = ui.BokehWidget()

    def observe(self, ctrl):
        super().observe(ctrl)

        plot = self._plot
        def _onUpdateGlobal(**items):
            if 'current.track' in items or 'current.bead' in items:
                plot.plot = plotbead(ctrl)

        ctrl.observe(_onUpdateGlobal)
