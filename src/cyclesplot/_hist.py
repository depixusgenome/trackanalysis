#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Building a projection of phase 5"

import  warnings
from    abc            import ABC

from    bokeh.plotting import figure, Figure
from    bokeh.models   import LinearAxis, ColumnDataSource, Range1d

import  numpy        as np

from    view.plots          import PlotAttrs, checksizes
from    view.plots.sequence import SequenceTicker, estimatebias

class HistMixin(ABC):
    "Building a projection of phase 5 onto the Z axis"
    def __init__(self):
        "sets up this plotter's info"
        self.css.defaults = {'frames'    : PlotAttrs('white', 'quad',   1,
                                                     line_color = 'gray',
                                                     fill_color = 'gray'),
                             'cycles'    : PlotAttrs('white', 'quad',   1,
                                                     fill_color = None,
                                                     line_alpha = .5,
                                                     line_color = 'blue'),
                             'figure.width' : 450,
                             'figure.height': 450}
        self.css.hist.defaults = {'xtoplabel'    : u'Cycles',
                                  'xlabel'       : u'Frames'}
        SequenceTicker.defaultconfig(self)

        self._histsource: ColumnDataSource = None
        self._hist:       Figure           = None
        self._ticker                       = SequenceTicker()

    @checksizes
    def __data(self, data, shape):
        bins  = np.array([-1, 1])
        zeros = np.zeros((1,), dtype = 'f4')
        items = (zeros,)
        if shape != (1, 0):
            phase = self.config.root.phase.measure.get()
            zvals = data['z'].reshape(shape)
            if self._model.eventdetection.task is None:
                track = self._model.track
                ind1  = track.phases[:,phase]  -track.phases[:,0]
                ind2  = track.phases[:,phase+1]-track.phases[:,0]
                items = [val[ix1:ix2] for ix1, ix2, val in zip(ind1, ind2, zvals)]
            else:
                items = zvals

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category = RuntimeWarning)
                rng = (np.nanmin([np.nanmin(i) for i in items]),
                       np.nanmax([np.nanmax(i) for i in items]))
            if all(np.isfinite(i) for i in rng):
                width = self._model.binwidth
                bins  = np.arange(rng[0]-width*.5, rng[1]+width*1.01, width, dtype = 'f4')
                if bins[-2] > rng[1]:
                    bins = bins[:-1]

                size  = len(bins)-1
                items = [np.bincount(np.digitize(i, bins), minlength = size+1)[1:][:size]
                         for i in items]
                zeros = np.zeros((len(bins)-1,), dtype = 'f4')
            else:
                items = (zeros,)

        threshold = self._model.minframes
        return dict(frames  = np.sum(items, axis = 0),
                    cycles  = np.sum([np.int32(i > threshold) for i in items], axis = 0),
                    left    = zeros,
                    bottom  = bins[:-1],
                    top     = bins[1:])

    def _createhist(self, data, shape, yrng):
        self._hist       = figure(**self._figargs(self.css.hist,
                                                  y_axis_location = None,
                                                  x_range         = Range1d(0, 5e4),
                                                  y_range         = yrng,
                                                  name            = 'Cycles:Hist'))

        hist             = self.__data(data, shape)
        self._histsource = ColumnDataSource(hist)
        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 100.)}

        attrs = self.css.cycles.get()
        axis  = LinearAxis(x_range_name          = "cycles",
                           axis_label            = self.css.hist.xtoplabel.get(),
                           axis_label_text_color = attrs.line_color
                          )
        self._hist.add_layout(axis, 'above')

        self.css.frames.addto(self._hist,
                              source = self._histsource,
                              bottom = "bottom", top   = "top",
                              left   = "left",   right = "frames")

        attrs.addto(self._hist,
                    source = self._histsource,
                    bottom = "bottom", top   = "top",
                    left   = "left",   right = "cycles",
                    x_range_name = "cycles")

        self._ticker.create(self._hist, self._model, self)

        self._hover.createhist(self._hist, self._model, self)
        self._hover.slaveaxes(self._hist, self._histsource)

    def _histobservers(self):
        def _fcn():
            with self.resetting():
                self._ticker.reset(self._bkmodels)
                self._hover.resethist(self._bkmodels)
        self._model.observeprop('oligos', 'sequencepath', _fcn)

    def _resethist(self, data, shape):
        hist = self.__data(data, shape)

        self._model.estimatedbias = estimatebias(hist['bottom'], hist['cycles'])
        self._hover.resethist(self._bkmodels)
        self._ticker.reset(self._bkmodels)

        self._bkmodels[self._histsource]['data'] = hist
        self.setbounds(self._hist.y_range, 'y', data['z'])
