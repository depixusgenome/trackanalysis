#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional, Sequence, Tuple, List,
                                        cast, TYPE_CHECKING)

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import figure, Figure    # pylint: disable=unused-import
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        DataTable, TableColumn, Model, Widget)

import numpy                    as     np
from eventdetection.processor   import EventDetectionTask
from peakfinding.processor      import PeakSelectorTask
from peakfinding.selector       import PeakSelectorDetails
from peakcalling.processor      import (FitToHairpinTask, FitToHairpinProcessor,
                                        FitBead)

from view.base                  import enableOnTrack
from view.plots                 import (PlotView, PlotAttrs, from_py_func,
                                        WidgetCreator, DpxKeyedRow)
from view.plots.tasks           import (TaskPlotModelAccess, TaskPlotCreator,
                                        TaskAccess)
from view.plots.sequence        import (readsequence, SequenceTicker,
                                        SequenceHoverMixin, SequencePathWidget,
                                        OligoListWidget)

from ..probabilities            import  Probability
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
    updating  = props.String('')
    biases    = props.Dict(props.String, props.Float)
    stretches = props.Dict(props.String, props.Float)
    __implementation__ = SequenceHoverMixin.impl('PeaksSequenceHover',
                                                 '''
                                                 stretches: [p.Instance, {}],
                                                 biases:    [p.Instance, {}],
                                                 ''')
    def reset(self, **kwa):
        "Creates the hover tool for histograms"
        fits = self.model.fits
        if fits is None:
            kwa['biases'] = kwa['stretches'] = {}
        else:
            kwa['biases']    = {i: j.bias    for i, j in fits.distances}
            kwa['stretches'] = {i: j.stretch for i, j in fits.distances}
        super().reset(**kwa)

class PeaksSequencePathWidget(SequencePathWidget):
    "Widget for setting the sequence to use"
    def _sort(self, lst) -> List[str]:
        fcn  = lambda i: self._model.fits.distances[i].value
        return sorted(lst, key = fcn)

    def callbacks(self,
                  hover: SequenceHoverMixin,
                  tick1: SequenceTicker):
        "sets-up callbacks for the tooltips and grids"
        widget = super().callbacks(hover, tick1)

        @from_py_func
        def _js_cb(cb_obj, hvr = hover):
            if cb_obj.value in hvr.source.column_names:
                hvr.bias    = hvr.biases [cb_obj.value]
                hvr.stretch = hvr.stretch[cb_obj.value]
                hvr.updating = 'seq'
                hvr.updating = ''
        widget.js_on_change('value', _js_cb)

class PeaksStatsWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        self.css.title.stats.defaults = {'title' : u'keys',
                                         'value' : u'values'}

    def create(self, _) -> List[Widget]:
        cols = [TableColumn(field = i, title = self.css.title.stats[i].get())
                for i in ('title', 'value')]

        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = False,
                                  row_headers = False,
                                  name        = "Peaks:Stats")
        return [self.__widget]

    def observe(self):
        "sets-up config observers"
        self._model.observeprop('oligos', self.reset)

    def reset(self):
        self.__widget.source.data = self.__data()

    def __data(self) -> dict:
        titles = ['stretch', 'bias', 'σ[HF]', 'peak count',
                  'identified peaks', 'missing peaks']
        values = np.full((len(titles),), np.NaN, dtype = 'f4')
        if self._model.identification.task is not None:
            best      = self._model.sequencekey
            values[0] = self._model.fits.distances[best].stretch
            values[1] = self._model.fits.distances[best].bias
            values[2] = self._model.peakselection.task.rawprecision(self._model.track,
                                                                    self._model.bead)
            values[3] = len(self._model.fits.peaks)
            values[4] = np.sum(self._model.fits.peaks['key'] >= 0)
            values[5] = len(self._model.identification.task.peakids[best].peaks)-1
        return {'title': titles, 'value': values}

class PeakListWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        self.css.title.peaks.defaults = {'id'         : u'Id',
                                         'distance'   : u'Distance to Id',
                                         'count'      : u'Rate     (%)',
                                         'duration'   : u'Duration (s)',
                                         'sigma'      : u'σ (nm)'}

    def create(self, _) -> List[Widget]:
        cols = [TableColumn(field = 'bases',
                            title = self.css.yrightlabel.get()),
                TableColumn(field = 'z',
                            title = self.css.ylabel.get()),
                *(TableColumn(field = i, title = self.css.title.peaks[i].get())
                  for i in ('sigma', 'id', 'distance', 'count', 'duration'))]

        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = False,
                                  row_headers = True,
                                  name        = "Peaks:List")
        return [self.__widget]

    def observe(self):
        "sets-up config observers"
        self._model.observeprop('oligos', self.reset)

    def reset(self):
        self.__widget.source.data = self.__data()

    def __data(self) -> dict:
        if self._model.identification.task is None:
            return {}

        best   = self._model.sequencekey
        dist   = self._model.fits.distances[best][1:]
        alg    = self._model.identification.task.peakids[best]
        peaks  = alg(np.array([i for i, _ in self._model.fits.events], dtype = 'f4'),
                     *dist)

        res    = {i.field: np.empty((len(peaks),), dtype = 'f4')
                  for i in self.__widget.columns} # pylint: disable=not-an-iterable
        res.update(dict(bases = peaks['zvalue']*dist[0]+dist[1],
                        z     = peaks['zvalue'],
                        id    = np.float32(peaks['key']))) # type: ignore
        res['id'][res['id'] < 0] = np.NaN
        res['distance'] = res['bases'] - res['id']

        prob = Probability(framerate   = self._model.track.framerate,
                           minduration = (self._model.eventdetection.task
                                          .events.selection.minduration))
        dur  = self._model.track.phaseduration(..., self._model.eventdetection.task.phase)
        ncyc = self._model.track.ncycles
        for i, (_, evts) in enumerate(self._model.fits.events):
            val = prob(evts, dur)
            res['sigma'][i]    = np.nanstd([np.nanmean(evt) for evt in evts])
            res['duration'][i] = val.averageduration
            res['count'][i]    = min(1., val.nevents / ncyc)
        return res

class PeaksPlotCreator(TaskPlotCreator):
    "Creates plots for peaks"
    _MODEL = PeaksPlotModelAccess
    _RESET = TaskPlotCreator._RESET | {'oligos', 'last.track.fasta'}
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

        self._source  = ColumnDataSource()
        self._fig     = None # type: Optional[Figure]
        self._widgets = dict(seq    = PeaksSequencePathWidget(self._model),
                             oligos = OligoListWidget(self._model),
                             stats  = PeaksStatsWidget(self._model),
                             peaks  = PeakListWidget(self._model))
        self._ticker  = SequenceTicker()
        self._hover   = PeaksSequenceHover()
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
        frate = track.framerate
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
        axis = LinearAxis(x_range_name = "duration", axis_label = self.css.xtoplabel.get())
        self._fig.add_layout(axis, 'above')
        self._hover.slaveaxes(self._fig, self._source, "duration", "z")

        widgets = {i: j.create(self.action) for i, j in self._widgets.items()}
        enableOnTrack(self, self._fig, *widgets.values())

        self._addcallbacks(self._fig)
        self._widgets['seq'].callbacks(self._hover.source, self._ticker)

        self._widgets['stats'].observe()
        self._widgets['peaks'].observe()
        self.configroot.observe(self.reset)
        return layouts.row([DpxKeyedRow(self, self._fig),
                            layouts.widgetbox([self._widgets['seq'],
                                               self._widgets['oligos'],
                                               self._widgets['stats'],
                                               self._widgets['peaks']])])

    def _reset(self, _):
        self._source.data, dtl = self.__data()
        self._model.setfits(dtl)
        self._hover .reset()
        self._ticker.reset()
        self._hover.slaveaxes(self._fig, self._source, "duration", "z", inpy = True)

class PeaksPlotView(PlotView):
    "Peaks plot view"
    PLOTTER = PeaksPlotCreator
