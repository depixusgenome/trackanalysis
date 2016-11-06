#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from bokeh.plotting  import figure
from .               import FlexxView, ui

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

    def _add(beadname, beadvalues):
        glyph = ctrl.getConfig(key+beadname+".glyph")
        args  = dict(x     = items['t'],
                     y     = items[beadvalues],
                     color = ctrl.getConfig(key+beadname+".color"),
                     size  = ctrl.getConfig(key+beadname+".size")
                    )
        if glyph == 'line':
            args['line_width'] = args.pop('size')
        getattr(fig, glyph)(**args)

    fig = figure(tools=ctrl.getConfig(key+"tools"))
    _add("zmag", "zmag")
    _add("z", bead)
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
