#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional, Sequence, Tuple,
                                        cast, TYPE_CHECKING)

import bokeh.core.properties as props
from bokeh.plotting             import figure, Figure    # pylint: disable=unused-import
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        Model)

import numpy                    as     np
from eventdetection.processor   import EventDetectionTask
from peakfinding.processor      import PeakSelectorTask
from peakfinding.selector       import PeakSelectorDetails
from peakcalling.processor      import (FitToHairpinTask, FitToHairpinProcessor,
                                        FitBead)

from view.plot                  import PlotView, PlotAttrs
from view.plot.tasks            import (TaskPlotModelAccess, TaskPlotCreator,
                                        TaskAccess)
from view.plot.sequence         import readsequence, SequenceTicker, SequenceHoverMixin

def sequenceprop(attr):
    "create a property which updates the FitToHairpinTask as well"
    def _getter(self):
        return self.configroot[attr].get()

    def _setter(self, val):
        self.configroot[attr].set(val)
        ols  = self.configroot['oligos']
        seq  = self.configroot['last.path.fasta']
        if ols is None or len(ols) == 0 or len(readsequence(seq)) == 0:
            self.identification.remove()
        else:
            self.identification.update(**FitToHairpinTask.read(seq, ols).config())
        return val

    hmsg  = "link to config's {}".format(attr)
    return property(_getter, _setter, None, hmsg)

class PeaksPlotModelAccess(TaskPlotModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        self.eventdetection = TaskAccess(self, EventDetectionTask)
        self.peakselection  = TaskAccess(self, PeakSelectorTask)
        self.identification = TaskAccess(self, FitToHairpinTask)
        self.fits           = None # type: Optional[FitBead]

    sequencepath = cast(Optional[str],           sequenceprop('last.path.fasta'))
    oligos       = cast(Optional[Sequence[str]], sequenceprop('oligos'))

    def setfits(self, dtl) -> Optional[FitBead]:
        "sets current bead fit"
        if dtl is None or self.identification.task is None:
            self.fits = None
        else:
            vals = self.peakselection.task.details2output(dtl)
            cnf  = self.identification.task.config()
            self.fits = FitToHairpinProcessor.compute(vals, **cnf)[1]
        return self.fits

class PeaksSequenceHover(Model, SequenceHoverMixin):
    "tooltip over peaks"
    framerate = props.Float(1.)
    bias      = props.Float(0.)
    stretch   = props.Float(0.)
    biases    = props.Dict(props.String, props.Float)
    stretches = props.Dict(props.String, props.Float)
    __implementation__ = SequenceHoverMixin.impl('PeaksSequenceHover', '')

class PeaksPlotCreator(TaskPlotCreator):
    "Creates plots for peaks"
    _MODEL = PeaksPlotModelAccess
    def __init__(self, *args):
        super().__init__(*args)
        self.css.defaults = {'duration'        : PlotAttrs('white', 'quad',   1,
                                                           line_color = 'gray',
                                                           fill_color = 'gray'),
                             'count'           : PlotAttrs('white', 'quad',   1,
                                                           fill_color = None,
                                                           line_alpha = .5,
                                                           line_color = 'blue'),
                             'xtoplabel'       : u'Duration (s)',
                             'xlabel'          : u'Cycles (%)',
                             'toolbar_location': 'right',
                             **SequenceTicker.defaultconfig()
                            }
        self.config.defaults = {'tools'      : 'ypan,ybox_zoom,reset,save,dpxhover'}

        self._source = ColumnDataSource()
        self._fig    = None # type: Optional[Figure]
        self._ticker = SequenceTicker()
        self._hover  = PeaksSequenceHover()
        if TYPE_CHECKING:
            self._model = PeaksPlotModelAccess('', '')

    def _figargs(self, _ = None):
        args = super()._figargs(_)
        args['x_axis_label']     = self.css.xlabel.get()
        args['y_axis_label']     = self.css.ylabel.get()
        args['toolbar_location'] = 'right'
        args['y_range']          = Range1d(start = 0., end = 0.)
        args['name']             = 'Peaks:Fig'
        return args

    def __data(self) -> Tuple[dict, PeakSelectorDetails]:
        cycles = self._model.runbead()
        data   = dict.fromkeys(('z', 'suration', 'count'), [0., 1.])
        if cycles is None:
            return data, None

        items = list(cycles)
        if len(items) == 0 or not any(len(i) for _, i in items):
            return data, None

        track = self._model.track
        peaks = self._model.peakselection.task
        prec  = peaks.rawprecision(track, self._model.bead)
        dtl   = peaks.detailed(items, prec)
        frate = self._model.framerate
        lens  = np.array([np.array([len(i)*frate for i in j], dtype = 'i4') for j in items],
                         dtype = 'O')

        hist  = peaks.histogram
        data  = dict(z        = np.arange(dtl.minv,
                                          (len(dtl.hist)+0.001)*dtl.binwidth+dtl.minv,
                                          dtl.binwidth, dtype = 'f4'),
                     count    = dtl.hist/track.ncycles,
                     duration = hist(dtl.pos, weights = lens, zmeasure = None)
                    )
        return data, dtl

    def _create(self, doc):
        "returns the figure"
        self._fig            = figure(**self._figargs())
        self._source.data, _ = self.__data()
        self._hover.create(self._fig, self._model, self)
        doc.add_root(self._hover)

        self.css.duration.addto(self._fig, x = 'z', y = 'duration', source = self._source)
        self.css.count   .addto(self._fig, x = 'z', y = 'count',    source = self._source)

        self._ticker.create(self._fig, self._model, self)

        self._fig.extra_x_ranges = {"duration": Range1d(start = 0., end = 0.)}
        axis = LinearAxis(x_range_name="duration", axis_label = self.css.xtoplabel.get())
        self._fig.add_layout(axis, 'above')
        self._addcallbacks(self._fig)
        self._hover.slaveaxes(self._hist, self._histsource, "duration", "z")

    def _reset(self, _):
        self._source.data, dtl = self.__data()
        self._model.setfits(dtl)
        self._hover .reset()
        self._ticker.reset()
        self._hover.slaveaxes(self._hist, self._histsource, "duration", "z", inpy = True)

class PeaksPlotView(PlotView):
    "Peaks plot view"
    PLOTTER = PeaksPlotCreator
