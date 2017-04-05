#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional, Sequence, Tuple, List, Dict,
                                        Generic, TypeVar, TYPE_CHECKING)

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import figure, Figure    # pylint: disable=unused-import
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        DataTable, TableColumn, Model, Widget,
                                        Div, NumberFormatter)

import numpy                    as     np

from signalfilter               import rawprecision
from control.taskio             import ConfigTrackIO
from control.processor          import processors
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.processor      import PeakSelectorTask
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

class FitParamProp(TaskPlotModelAccess.props.config[float]):
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
            val = super().__get__(obj, tpe)
            if val is None:
                return getattr(obj, 'estimated'+self.__key)
            return val
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
        self.eventdetection     = TaskAccess(self, EventDetectionTask)
        self.peakselection      = TaskAccess(self, PeakSelectorTask)
        self.identification     = TaskAccess(self, FitToHairpinTask)
        self.fits               = None   # type: Optional[FitBead]
        self.peaks              = dict() # type: Dict[str, np.ndarray]
        self.estimatedstretch   = 1.
        self.estimatedbias      = 0.

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
    def distances(self) -> Dict[str,Tuple[float,...]]:
        "returns the distances which were computed"
        return self.fits.distances if self.fits is not None else {}

    def setpeaks(self, dtl) -> Optional[FitBead]:
        "sets current bead peaks and computes the fits"
        if dtl is None:
            self.peaks = dict.fromkeys(('z', 'id', 'distance', 'sigma', 'bases',
                                        'duration', 'count'), [])
            self.fits  = None
            return

        nan        = lambda: np.full((len(peaks),), '', dtype = 'O')
        peaks      = tuple(self.peakselection.task.details2output(dtl))
        self.peaks = dict(z        = np.array([i for i, _ in peaks], dtype = 'f4'),
                          id       = nan(),
                          distance = nan(),
                          sigma    = nan(),
                          duration = nan(),
                          count    = nan())
        self.estimatedbias  = self.peaks['z'][0]
        self.peaks['bases'] = (self.peaks['z']-self.bias)/self.stretch

        task = self.identification.task
        if task is not None:
            cnf       = self.identification.task.config()
            self.fits = FitToHairpinProcessor.compute(peaks, **cnf)[1]

            tmp       = task.peakids[self.sequencekey](self.peaks['z'],
                                                       self.stretch,
                                                       self.bias)

            self.peaks['id'] = np.float32(tmp['key']) # type: ignore
            self.peaks['id'][self.peaks['id'] < 0] = ''
            self.peaks['distance'] = self.peaks['bases'] - self.peaks['id']

        prob = Probability(framerate   = self.track.framerate,
                           minduration = (self.eventdetection.task
                                          .events.select.minduration))
        dur  = self.track.phaseduration(..., self.eventdetection.task.phase)
        ncyc = self.track.ncycles
        for i, (_, evts) in enumerate(peaks):
            val                       = prob(evts, dur)
            self.peaks['duration'][i] = val.averageduration
            self.peaks['sigma'][i]    = prob.resolution(evts)
            self.peaks['count'][i]    = min(100., val.nevents / ncyc*100.)

        return self.peaks

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

    def reset(self):
        "Creates the hover tool for histograms"
        dist = self._model.distances
        super().reset(biases    = {i: j.bias    for i, j in dist},
                      stretches = {i: j.stretch for i, j in dist})

    def slaveaxes(self, fig, src, inpy = False): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        # pylint: disable=too-many-arguments,protected-access
        hvr = self
        def _onchangebounds(fig = fig, hvr = hvr, src = src):
            yrng = fig.y_range
            if hasattr(yrng, '_initial_start') and yrng.bounds is not None:
                yrng._initial_start = yrng.bounds[0]
                yrng._initial_end   = yrng.bounds[1]

            bases        = fig.extra_y_ranges['bases']
            bases.start  = (yrng.start - hvr.bias)/hvr.stretch
            bases.end    = (yrng.end   - hvr.bias)/hvr.stretch

            zval = src.data["z"]
            ix1  = 0
            ix2  = len(zval)
            for i in range(ix2):
                if zval[i] < yrng.start:
                    ix1 = i+1
                    continue
                if zval[i] > yrng.end:
                    ix2 = i
                    break

            dur = fig.extra_x_ranges['duration']
            cnt = fig.x_range

            dur.start = 0.
            cnt.start = 0.
            if len(zval) < 2 or ix1 == ix2:
                dur.end = 0.
                cnt.end = 0.
            else:
                dur.end = max(src.data["duration"][ix1:ix2])
                cnt.end = max(src.data["count"][ix1:ix2])

        if inpy:
            _onchangebounds()
        else:
            fig.y_range.callback = from_py_func(_onchangebounds)

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
        self.__widget = None # type: Optional[Div]
        css = self.css.stats.lines
        css.default = [[u'Stretch (µm/base)',  '.4f'],
                       [u'Bias (µm)',          '.4f'],
                       [u'σ[HF] (µm)',         '.4f'],
                       [u'σ[Peaks] (µm)',      '.4f'],
                       [u'Peak count',         '.0f'],
                       [u'Identified peaks',   '.0f'],
                       [u'Unknown peaks',      '.0f']]
    def create(self, _) -> List[Widget]:
        self.__widget = Div(text  = self.__data(),
                            width = self.css.input.width.get())
        return [self.__widget]

    def reset(self):
        self.__widget.text = self.__data()

    def __data(self) -> str:
        titles = self.css.stats.lines.get()
        values = ['']*len(titles) # type: List
        if self._model.identification.task is not None:
            best      = self._model.sequencekey
            values[5] = np.sum(self._model.fits.peaks['key'] >= 0)
            values[6] = (len(self._model.identification.task.peakids[best].peaks)-1
                         -values[4])

        if self._model.track is not None:
            values[0] = self._model.stretch
            values[1] = self._model.bias
            values[2] = rawprecision(self._model.track, self._model.bead)
            values[3] = np.mean(self._model.peaks['sigma'])
            values[4] = len(self._model.peaks['z'])

        line = '<tr><td>{}</td><td>{}</td></tr>'
        fcn  = lambda fmt, val: '' if val == '' else ('{:'+fmt+'}').format(val)
        tab  = ''.join(line.format(i[0], fcn(i[1], j))
                       for i, j in zip(titles, values))
        return '<table>'+tab+'</table>'

class PeakListWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        self.css.peaks.columns.default = [['z',          'css:ylabel',      '0.0[000]'],
                                          ['bases',      'css:yrightlabel', '0.[00]'],
                                          ['id',         u'Id',             '[0]'],
                                          ['distance',   u'Distance',       '0.[0]'],
                                          ['count',      'css:xlabel',      '0.[0]'],
                                          ['duration',   'css:xtoplabel',   '0.[000]'],
                                          ['sigma',      u'σ (µm)',         '0.0[000]']]

    def create(self, _) -> List[Widget]:
        width = self.cssroot.input.width.get()
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        cols  = list(TableColumn(field     = i[0],
                                 title     = get(i[1]),
                                 formatter = NumberFormatter(format = i[2]))
                     for i in self.css.peaks.columns.get())
        self.__widget = DataTable(source      = ColumnDataSource(self._model.peaks),
                                  columns     = cols,
                                  editable    = False,
                                  row_headers = False,
                                  width       = width*len(cols),
                                  name        = "Peaks:List")
        return [self.__widget]

    def setsource(self, src):
        "this widget has a source in common with the plots"
        self.__widget.source = src

    def reset(self):
        pass

class PeaksPlotCreator(TaskPlotCreator):
    "Creates plots for peaks"
    _MODEL = PeaksPlotModelAccess
    def __init__(self, *args):
        super().__init__(*args)
        self.css.defaults = {'duration'        : PlotAttrs('gray', 'line', 1),
                             'count'           : PlotAttrs('blue', 'line', 1),
                             'plot.width'      : 500,
                             'plot.height'     : 800,
                             'xtoplabel'       : u'Duration (s)',
                             'xlabel'          : u'Rate (%)'}
        self.css.peaks.defaults = {'duration'  : PlotAttrs('gray', 'diamond', 5),
                                   'count'     : PlotAttrs('blue', 'circle', 5)}
        self.config.defaults = {'tools'      : 'ypan,ybox_zoom,reset,save,dpxhover'}
        PeaksSequenceHover.defaultconfig(self)
        SequenceTicker.defaultconfig(self)

        self._histsrc = None # type: Optional[ColumnDataSource]
        self._peaksrc = None # type: Optional[ColumnDataSource]
        self._fig     = None # type: Optional[Figure]
        self._widgets = dict(seq    = PeaksSequencePathWidget(self._model),
                             oligos = OligoListWidget(self._model),
                             stats  = PeaksStatsWidget(self._model),
                             peaks  = PeakListWidget(self._model))
        self._ticker  = SequenceTicker()
        self._hover   = PeaksSequenceHover()
        if TYPE_CHECKING:
            self._model = PeaksPlotModelAccess('', '')

    def __data(self) -> Tuple[dict, dict]:
        cycles = self._model.runbead()
        data   = dict.fromkeys(('z', 'duration', 'count'), [0., 1.])
        self._model.setpeaks(None)
        if cycles is None:
            return data, self._model.peaks

        items = tuple(i for _, i in cycles)
        if len(items) == 0 or not any(len(i) for i in items):
            return data, self._model.peaks

        peaks = self._model.peakselection.task
        if peaks is None:
            return data, self._model.peaks

        track = self._model.track
        dtl   = peaks.detailed(items, rawprecision(track, self._model.bead))

        maxv  = max(peaks.histogram.kernelarray())
        data  = dict(z     = (dtl.binwidth*np.arange(len(dtl.histogram), dtype = 'f4')
                              +dtl.minvalue),
                     count = dtl.histogram/(maxv*track.ncycles)*100.)

        return data, self._model.setpeaks(dtl)

    def _create(self, doc):
        "returns the figure"
        self._fig = figure(**self._figargs(y_range = Range1d, name = 'Peaks:fig'))
        self._fig.extra_x_ranges = {"duration": Range1d(start = 0., end = 0.)}
        axis  = LinearAxis(x_range_name          = "duration",
                           axis_label            = self.css.xtoplabel.get(),
                           axis_label_text_color = self.css.duration.get().color
                          )
        self._fig.add_layout(axis, 'above')

        self._histsrc, self._peaksrc = (ColumnDataSource(i) for i in self.__data())

        self.css.count         .addto(self._fig, y = 'z', x = 'count',
                                      source       = self._histsrc)
        self.css.peaks.count   .addto(self._fig, y = 'z', x = 'count',
                                      source       = self._peaksrc)
        self.css.peaks.duration.addto(self._fig, y = 'z', x = 'duration',
                                      source       = self._peaksrc,
                                      x_range_name = "duration")

        self._hover.create(self._fig, self._model, self)
        doc.add_root(self._hover)

        self._ticker.create(self._fig, self._model, self)
        self._hover.slaveaxes(self._fig, self._peaksrc)

        widgets = {i: j.create(self.action) for i, j in self._widgets.items()}
        enableOnTrack(self, self._fig, widgets)

        self._addcallbacks(self._fig)
        self._widgets['seq'].callbacks(self._hover, self._ticker)
        self._widgets['peaks'].setsource(self._peaksrc)

        self.configroot.observe(self.reset)

        # pylint: disable=redefined-variable-type
        width = widgets['peaks'][-1].width+10
        lay   = layouts.widgetbox(*widgets['seq'], *widgets['oligos'],
                                  width       = self.css.input.width.get()+10,
                                  sizing_mode = self.css.sizing_mode.get())
        lay = layouts.row(lay, layouts.widgetbox(*widgets['stats']),
                          width       = self.css.input.width.get()*2,
                          sizing_mode = self.css.sizing_mode.get())
        lay = layouts.column(lay, *widgets['peaks'],
                             sizing_mode = self.css.sizing_mode.get(),
                             width       = width)
        return layouts.row(DpxKeyedRow(self, self._fig), lay)

    def _reset(self, _):
        data, self._peaksrc.data = self.__data()
        self._histsrc.data       = data
        self._hover .reset()
        self._ticker.reset()
        for widget in self._widgets.values():
            widget.reset()

        self.setbounds(self._fig.y_range, 'y', data['z'][[0,-1]])
        self._hover.slaveaxes(self._fig, self._peaksrc, inpy = True)

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
