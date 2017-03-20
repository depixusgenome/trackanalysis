#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Building a projection of phase 5"

from typing         import Optional, Any, TYPE_CHECKING   # pylint: disable=unused-import

from    bokeh.plotting import figure, Figure    # pylint: disable=unused-import
from    bokeh.models   import LinearAxis, ColumnDataSource, CustomJS, Range1d

import numpy        as np

from  ..plotutils  import PlotAttrs, checksizes
from   ._bokehext  import DpxFixedTicker

window = None # type: Any # pylint: disable=invalid-name

class HistMixin:
    "Building a projection of phase 5 onto the Z axis"

    __PHASE = 5
    def __init__(self):
        "sets up this plotter's info"
        css = self.getCSS()
        css.defaults = {'frames'    : PlotAttrs('white', 'quad',   1,
                                                line_color = 'gray',
                                                fill_color = 'gray'),
                        'cycles'    : PlotAttrs('white', 'quad',   1,
                                                fill_color = None,
                                                line_alpha = .5,
                                                line_color = 'blue'),
                        **DpxFixedTicker.defaultconfig()
                       }
        css.hist.defaults = dict(xtoplabel = u'Cycles',
                                 xlabel    = u'Frames',
                                 ylabel    = u'Base number',
                                 plotwidth = 200)

        self._histsource = None # type: Optional[ColumnDataSource]
        self._hist       = None # type: Optional[Figure]
        self._gridticker = None # type: Optional[DpxFixedTicker]

    @checksizes
    def __data(self, track, data, shape):
        if shape == (1, 2):
            bins  = np.array([-1, 1])
            zeros = np.zeros((1,), dtype = 'f4')
            items = zeros,
        else:
            zvals = data['z'].reshape(shape)
            ind1  = track.phases[:,self.__PHASE]  -track.phases[:,0]
            ind2  = track.phases[:,self.__PHASE+1]-track.phases[:,0]
            items = [val[ix1:ix2] for ix1, ix2, val in zip(ind1, ind2, zvals)]

            rng   = (np.nanmin([np.nanmin(i) for i in items]),
                     np.nanmax([np.nanmax(i) for i in items]))

            width = self._model.binwidth
            bins  = np.arange(rng[0]-width*.5, rng[1]+width*1.01, width, dtype = 'f4')
            if bins[-2] > rng[1]:
                bins = bins[:-1]

            items = [np.bincount(np.digitize(i, bins), minlength = len(bins))[1:]
                     for i in items]
            zeros = np.zeros((len(bins)-1,), dtype = 'f4')

        threshold = self._model.minframes
        return dict(frames  = np.sum(items, axis = 0),
                    cycles  = np.sum([np.int32(i > threshold) for i in items], axis = 0),
                    left    = zeros,
                    bottom  = bins[:-1],
                    top     = bins[1:])

    def _slavexaxis(self):
        # pylint: disable=protected-access,no-member
        def _onchangebounds(hist = self._hist, mdl = self._hover, src= self._histsource):
            yrng = hist.y_range
            if yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            cycles       = hist.extra_x_ranges["cycles"]
            frames       = hist.x_range

            cycles.start = 0.
            frames.start = 0.

            bases        = hist.extra_y_ranges['bases']
            bases.start  = (yrng.start-mdl.bias)/mdl.stretch
            bases.end    = (yrng.end-mdl.bias)/mdl.stretch

            bottom = src.data["bottom"]
            delta  = bottom[1]-bottom[0]

            ind1   = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
            ind2   = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

            if ind1 >= ind2:
                return

            frames.end = window.Math.max.apply(None, src.data['frames'][ind1:ind2])+1
            cycles.end = window.Math.max.apply(None, src.data['cycles'][ind1:ind2])+1

        self._hist.y_range.callback = CustomJS.from_py_func(_onchangebounds)

    def _createhist(self, track, data, shape, yrng):
        css              = self.getCSS()
        self._hist       = figure(y_axis_location = None,
                                  y_range         = yrng,
                                  name            = 'Cycles:Hist',
                                  **self._figargs(css.hist))

        hist             = self.__data(track, data, shape)
        self._histsource = ColumnDataSource(data = hist)
        self._hist.extra_x_ranges = {"cycles": Range1d(start = 0., end = 0.)}

        attrs = css.cycles.get()
        axis  = LinearAxis(x_range_name          = "cycles",
                           axis_label            = css.hist.xtoplabel.get(),
                           axis_label_text_color = attrs.line_color
                          )
        self._hist.add_layout(axis, 'above')

        css.frames.addto(self._hist,
                         source = self._histsource,
                         bottom = "bottom", top   = "top",
                         left   = "left",   right = "frames")

        attrs.addto(self._hist,
                    source = self._histsource,
                    bottom = "bottom", top   = "top",
                    left   = "left",   right = "cycles",
                    x_range_name = "cycles")

        self._gridticker = DpxFixedTicker()
        self._gridticker.create(self.getCSS(), self._hist)
        self._gridticker.observe(self.getRootConfig(), self._model, self._hist)

        self._hover.createhist(self._hist, self._model, self.getCSS(), self.getConfig())
        self._hover.observe(self.getRootConfig(), self.getConfig(), self._model)
        self._slavexaxis()

    def _updatehist(self, track, data, shape):
        self._histsource.data = hist = self.__data(track, data, shape)
        self._hover.updatehist(self._hist, hist, self._model, self.getConfig())
        self._gridticker.updatedata(self._model, self._hist)

        bottom = self._histsource.data["bottom"]
        delta  = bottom[1]-bottom[0]

        cycles = self._hist.extra_x_ranges["cycles"]
        frames = self._hist.x_range
        yrng   = self._hist.y_range

        ind1   = min(len(bottom), max(0, int((yrng.start-bottom[0])/delta-1)))
        ind2   = min(len(bottom), max(0, int((yrng.end  -bottom[0])/delta+1)))

        if ind1 >= ind2:
            cycles.start = 0
            frames.start = 0
        else:
            cycles.update(start = 0, end = max(self._histsource.data['cycles'][ind1:ind2])+1)
            frames.update(start = 0, end = max(self._histsource.data['frames'][ind1:ind2])+1)

    if TYPE_CHECKING:
        getConfig = getCSS = lambda: None
