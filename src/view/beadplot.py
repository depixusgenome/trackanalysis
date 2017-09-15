#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Track plot view"
from bokeh.plotting import figure, Figure
from bokeh.models   import LinearAxis, ColumnDataSource, Range1d

from control            import Controller
from .plots             import PlotAttrs, DpxKeyedRow, PlotView
from .plots.bokehext    import DpxHoverTool, from_py_func
from .plots.tasks       import TaskPlotCreator

class BeadPlotCreator(TaskPlotCreator):
    "Plots a default bead"
    def __init__(self,  ctrl:Controller) -> None:
        "sets up this plotter's info"
        super().__init__(ctrl)
        ttips = [(u'Index', '$index'), (u'(t, z, zmag)', '($~x, $data_y, @zmag)')]
        self.css.defaults = {'z':               PlotAttrs('lightblue', 'circle', 1),
                             'zmag':            PlotAttrs('red',  'line',   1),
                             'xlabel':          u"Frames",
                             'ylabel':          u"Z",
                             'yrightlabel':     u"Zmag",
                             'tooltips':        ttips,
                             'figure.width' :   900,
                             'figure.height':   600}
        self._source: ColumnDataSource = None
        self._fig:    Figure           = None

    def __data(self):
        track = self._model.track
        bead  = self._model.bead
        if track is None:
            return dict.fromkeys(('t', 'zmag', 'z'), [])
        items = track.beads
        return dict(t    = items['t'],
                    zmag = items['zmag'],
                    z    = items[bead])

    def _addglyph(self, beadname, **kwa):
        return self.css[beadname].addto(self._fig,
                                        x      = 't',
                                        y      = beadname,
                                        source = self._source,
                                        **kwa)

    def _addylayout(self):
        cnf = self.css
        self._fig.extra_y_ranges = {'zmag': Range1d(start = 0., end = 1.)}
        axis  = LinearAxis(y_range_name          = 'zmag',
                           axis_label            = cnf.yrightlabel.get(),
                           axis_label_text_color = cnf.zmag.get().color,
                          )
        self._fig.add_layout(axis, 'right')

    def _addcallbacks(self, fig):
        super()._addcallbacks(fig)
        rng = self._fig.extra_y_ranges['zmag']
        def _onRangeChange(rng = rng):
            rng.start = rng.bounds[0]
            rng.end   = rng.bounds[1]

        rng.callback = from_py_func(_onRangeChange)

    def _create(self, _) -> DpxKeyedRow:
        "sets-up the figure"
        self._fig    = figure(**self._figargs(x_range = Range1d,
                                              y_range = Range1d,
                                              name    = 'Bead:Fig'))
        self._source = ColumnDataSource(self.__data())
        if self.css.tooltips.get() not in ('', None):
            self._fig.select(DpxHoverTool).tooltips = self.css.tooltips.get()

        self._addylayout  ()
        self._addglyph    ('zmag', y_range_name = 'zmag')
        self._addglyph    ('z')
        for rng in self._fig.x_range, self._fig.y_range, self._fig.extra_y_ranges['zmag']:
            self.fixreset(rng)

        self._addcallbacks(self._fig)
        return DpxKeyedRow(self, self._fig)

    def _reset(self):
        self._bkmodels[self._source]['data'] = data = self.__data()
        self.setbounds(self._fig.extra_y_ranges['zmag'], None, data['zmag'])
        self.setbounds(self._fig.x_range,                 'x', data['t'])
        self.setbounds(self._fig.y_range,                 'y', data['z'])

class BeadPlotView(PlotView):
    "Bead plot view"
    PLOTTER = BeadPlotCreator
