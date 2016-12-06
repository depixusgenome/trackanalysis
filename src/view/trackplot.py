#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Track plot view"

from typing         import Optional  # pylint: disable=unused-import
from bokeh.plotting import figure
from bokeh.models   import (LinearAxis, Range1d, ColumnDataSource, HoverTool,
                            CustomJS)

from control        import Controller
from .plotutils     import SinglePlotter, PlotAttrs, KeyedRow
from .              import BokehView

class BeadPlotter(SinglePlotter):
    u"Plots a default bead"
    def __init__(self,  ctrl:Controller) -> None:
        u"sets up this plotter's info"
        super().__init__(ctrl)
        self._source = ColumnDataSource()
        self._fig    = figure(**self._figargs())

        cnf = ctrl.getGlobal(self.key())
        cnf.defaults = dict(z        = PlotAttrs('blue', 'circle', 1),
                            zmag     = PlotAttrs('red',  'line',   1),
                            tooltips = [(u'Index',  '$index'),
                                        (u'(t, z, zmag)', '($x, @z, @zmag)')])

    def _get(self, name):
        return self._source.data[name] # pylint: disable=unsubscriptable-object

    def _createdata(self):
        cnf         = self._ctrl.getGlobal("current")
        task        = cnf.track.get(default = None)
        if task is None:
            return dict.fromkeys(('t', 'zmag', 'z'), [0., 1.])

        items = next(iter(self._ctrl.run(task, task)))
        bead  = cnf.bead.get(default = None)
        if bead is None:
            bead = next(iter(items.keys()))

        return dict(t    = items['t'],
                    zmag = items['zmag'],
                    z    = items[bead])

    def _figargs(self):
        args = super()._figargs()
        args.update(x_axis_label = u'Time',
                    y_axis_label = u'z')
        return args

    def _addglyph(self, beadname, **kwa):
        self.getConfig()[beadname].addto(self._fig,
                                         x      = 't',
                                         y      = beadname,
                                         source = self._source,
                                         **kwa)

    def _addylayout(self):
        self._fig.extra_y_ranges = {'zmag': Range1d(start = 0., end = 1.)}
        self._fig.add_layout(LinearAxis(y_range_name='zmag', axis_label = u'zmag'), 'right')

    def _addcallbacks(self, fig):
        super()._addcallbacks(fig)
        rng = self._fig.extra_y_ranges['zmag']
        def _onRangeChange(rng = rng):
            rng.start = rng.bounds[0]
            rng.end   = rng.bounds[1]

        rng.callback = CustomJS.from_py_func(_onRangeChange)

    def _setbounds(self):
        self.setbounds(self._fig.extra_y_ranges['zmag'], None, self._get('zmag'))
        self.setbounds(self._fig.x_range, 'x', self._get('t'))
        self.setbounds(self._fig.y_range, 'y', self._get('z'))

    def _create(self):
        u"sets-up the figure"
        self._source = ColumnDataSource(data = self._createdata())
        self._fig.add_tools(HoverTool(tooltips = self.getConfig().tooltips.get()))

        self._addylayout  ()
        self._addglyph    ("zmag", y_range_name = 'zmag')
        self._addglyph    ("z")
        return self._fig

    def update(self, items:dict):
        u"Updates the data"
        if not ('track' in items or 'bead' in items):
            return

        with self.updating():
            self._source.data = self._createdata()
            self._setbounds()

class TrackPlot(BokehView):
    u"Track plot view"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._plotter = BeadPlotter(self._ctrl) # must change this to a Plot Factory
        self._ctrl.observe("globals.current", self._onUpdateCurrent)

    def close(self):
        u"remove controller"
        super().close()
        self._plotter.close()
        self._plotter = None

    def _onUpdateCurrent(self, **items):
        self._plotter.update(items)

    def getroots(self):
        u"adds items to doc"
        return KeyedRow(self._plotter),
