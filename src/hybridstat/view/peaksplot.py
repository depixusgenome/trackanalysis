#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional, Sequence, Tuple, List,
                                        Generic, TypeVar, TYPE_CHECKING)

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import figure, Figure    # pylint: disable=unused-import
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        DataTable, TableColumn, Model, Widget)

import numpy                    as     np

from signalfilter               import rawprecision
from control.taskio             import ConfigTrackIO
from control.processor          import processors
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
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

T = TypeVar('T')
class SequenceProp(TaskPlotModelAccess.props.configroot[T], Generic[T]):
    "A property which updates the FitToHairpinTask as well"
    def __set__(self, obj, val):
        super().__set__(obj, val)
        ols = obj.oligos
        seq = obj.sequencepath
        if ols is None or len(ols) == 0 or len(readsequence(seq)) == 0:
            obj.identification.remove()
        else:
            obj.identification.update(**FitToHairpinTask.read(seq, ols).config())
        return val

class FitParamProp(TaskPlotModelAccess.props.config[Optional[float]]):
    "access to bias or stretch"
    def __init__(self, attr):
        super().__init__('base.'+attr)
        self.__key = attr

    def __get__(self, obj, tpe) -> Optional[str]:
        if obj is None:
            return self
        key  = obj.sequencekey
        dist = obj.distances
        if key not in dist:
            return super().__get__(obj, tpe)
        else:
            return getattr(dist[key], self.__key)

    def __set__(self, obj, val):
        raise AttributeError("can't set attribute")

class SequenceKeyProp(TaskPlotModelAccess.props.bead[Optional[str]]):
    "access to the sequence key"
    def __init__(self):
        super().__init__('sequence.key')

    def __get__(self, obj, tpe) -> Optional[str]:
        "returns the current sequence key"
        if obj is None:
            return self
        key  = super().__get__(obj, tpe)
        if key is not None:
            return key

        if len(obj.distances):
            return min(obj.distances, key = obj.distances.__getitem__)

        dseq = readsequence(obj.sequencepath)
        return next(iter(dseq), None) if key not in dseq else key

class PeaksPlotModelAccess(TaskPlotModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        self.configroot.tasks.extremumalignment.default = ExtremumAlignmentTask()
        self.eventdetection = TaskAccess(self, EventDetectionTask)
        self.peakselection  = TaskAccess(self, PeakSelectorTask)
        self.identification = TaskAccess(self, FitToHairpinTask)
        self.fits           = None # type: Optional[FitBead]

        cls = type(self)
        cls.oligos      .setdefault(self, [], size = 4)
        cls.sequencekey .setdefault(self, None)   # type: ignore
        cls.stretch     .setdefault(self, 8.8e-4) # type: ignore
        cls.bias        .setdefault(self, None)   # type: ignore

    sequencekey  = SequenceKeyProp()
    sequencepath = SequenceProp[Optional[str]]('last.path.sequence')
    oligos       = SequenceProp[Optional[Sequence[str]]]('oligos')
    stretch      = FitParamProp('stretch')
    bias         = FitParamProp('bias')
    @property
    def distances(self) -> dict:
        "returns the distances which were computed"
        return self.fits.distances if self.fits is not None else {}

    def setfits(self, dtl) -> Optional[FitBead]:
        "sets current bead fit"
        if dtl is None or self.identification.task is None:
            self.fits = None
        else:
            vals = self.peakselection.task.details2output(dtl)
            cnf  = self.identification.task.config()
            self.fits = FitToHairpinProcessor.compute(vals, **cnf)[1]
        return self.fits

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        if self.track is None:
            return None

        root  = self.roottask
        ibead = self.bead
        task  = self.eventdetection.task
        if task is None:
            task  = self.configroot.tasks.eventdetection.get()
            ind   = self.eventdetection.index
            beads = next(iter(self._ctrl.run(root, ind-1, copy = True)))
            return next(processors(task)).apply(beads, **task.config())[ibead, ...]
        else:
            return next(iter(self._ctrl.run(root, task, copy = True)))[ibead, ...]

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
                                                 stretches: [p.Any, {}],
                                                 biases:    [p.Any, {}],
                                                 ''')

    def slaveaxes(self, fig, src, inpy = False): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        super().slaveaxes(fig, src, 'count', 'duration', 'z', inpy)

    def reset(self, hdata = None): # pylint: disable=arguments-differ
        "Creates the hover tool for histograms"
        kwa  = dict()
        bias = self._model.bias
        if bias is None:
            kwa['bias']  = self.estimatebias(hdata, 'duration', 'z')

        kwa['biases']    = {i: j.bias    for i, j in self._model.distances}
        kwa['stretches'] = {i: j.stretch for i, j in self._model.distances}
        super().reset(**kwa)

class PeaksSequencePathWidget(SequencePathWidget):
    "Widget for setting the sequence to use"
    def _sort(self, lst) -> List[str]:
        fcn  = lambda i: self._model.distances[i].value
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
        css = self.css.title.stats
        css.columns.defaults = {'title' : u'keys', 'value' : u'values'}
        css.lines.default = ['stretch', 'bias', 'σ[HF]', 'peak count',
                             'identified peaks', 'missing peaks']
    def create(self, _) -> List[Widget]:
        cols = [TableColumn(field = i, title = self.css.title.stats.columns[i].get())
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
        titles = self.css.title.stats.lines.get()
        values = np.full((len(titles),), np.NaN, dtype = 'f4')
        if self._model.identification.task is not None:
            best      = self._model.sequencekey
            values[0] = self._model.distances[best].stretch
            values[1] = self._model.distances[best].bias
            values[2] = rawprecision(self._model.track, self._model.bead)
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
        dist   = self._model.distances[best][1:]
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
    _RESET = TaskPlotCreator._RESET | {'oligos', 'last.track.sequence'}
    def __init__(self, *args):
        super().__init__(*args)
        self.css.defaults = {'duration'        : PlotAttrs('gray', 'line', 1),
                             'count'           : PlotAttrs('blue', 'line', 1),
                             'xtoplabel'       : u'Duration (s)',
                             'xlabel'          : u'Cycles (%)'}
        self.config.defaults = {'tools'      : 'ypan,ybox_zoom,reset,save,dpxhover'}
        PeaksSequenceHover.defaultconfig(self)
        SequenceTicker.defaultconfig(self)

        self._source  = None # type: Optional[ColumnDataSource]
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
        data   = dict.fromkeys(('z', 'duration', 'count'), [0., 1.])
        if cycles is None:
            return data, None

        items = tuple(i for _, i in cycles)
        if len(items) == 0 or not any(len(i) for i in items):
            return data, None

        peaks = self._model.peakselection.task
        if peaks is None:
            return data, None

        track = self._model.track
        frate = track.framerate
        prec  = rawprecision(track, self._model.bead)
        dtl   = peaks.detailed(items, prec)
        lens  = np.array([np.array([len(i)/frate for _, i in j], dtype = 'i4')
                          for j in items],
                         dtype = 'O')

        hist  = peaks.histogram
        data  = dict(z        = (dtl.binwidth*np.arange(len(dtl.histogram), dtype = 'f4')
                                 +dtl.minvalue),
                     count    = dtl.histogram/track.ncycles*100.,
                     duration = hist.projection(dtl.positions,
                                                weight    = lens,
                                                zmeasure  = None,
                                                precision = prec)[0]
                    )
        return data, dtl

    def _create(self, doc):
        "returns the figure"
        self._fig    = figure(**self._figargs())
        self._fig.extra_x_ranges = {"duration": Range1d(start = 0., end = 0.)}
        axis  = LinearAxis(x_range_name          = "duration",
                           axis_label            = self.css.xtoplabel.get(),
                           axis_label_text_color = self.css.duration.get().color
                          )
        self._fig.add_layout(axis, 'above')

        self._source = ColumnDataSource(self.__data()[0])
        self.css.count   .addto(self._fig, y = 'z', x = 'count',    source = self._source)
        self.css.duration.addto(self._fig, y = 'z', x = 'duration', source = self._source,
                                x_range_name = "duration")

        self._hover.create(self._fig, self._model, self)
        doc.add_root(self._hover)

        self._ticker.create(self._fig, self._model, self)
        self._hover.slaveaxes(self._fig, self._source)

        widgets = {i: j.create(self.action) for i, j in self._widgets.items()}
        enableOnTrack(self, self._fig, widgets)

        self._addcallbacks(self._fig)
        self._widgets['seq'].callbacks(self._hover, self._ticker)

        self._widgets['stats'].observe()
        self._widgets['peaks'].observe()
        self.configroot.observe(self.reset)
        box = layouts.widgetbox(*widgets['seq'], *widgets['oligos'], *widgets['peaks'],
                                sizing_mode = self.css.sizing_mode.get())
        return layouts.row(DpxKeyedRow(self, self._fig), box)

    def _reset(self, _):
        data, dtl = self.__data()
        self._source.data = data
        self.setbounds(self._fig.y_range, 'y', data['z'][[0,-1]])
        self._model.setfits(dtl)
        self._hover .reset(data)
        self._ticker.reset()
        self._hover.slaveaxes(self._fig, self._source, inpy = True)

class PeaksPlotView(PlotView):
    "Peaks plot view"
    PLOTTER = PeaksPlotCreator

    def ismain(self):
        "Alignment, ... is set-up by default"
        tasks         = self._ctrl.getGlobal('config').tasks
        tasks.default = ['extremumalignment', 'eventdetection', 'peakselector']
        ConfigTrackIO.setup(self._ctrl, tasks)

        trk = self._ctrl.getGlobal('project').track
        trk.observe(lambda itm: self._ctrl.clearData(itm.old))
