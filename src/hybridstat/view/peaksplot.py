#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional, Sequence, Tuple, List, Dict,
                                        Generic, TypeVar, Union, TYPE_CHECKING)

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import figure, Figure    # pylint: disable=unused-import
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        DataTable, TableColumn, Model, Widget,
                                        Div)

import numpy                    as     np

from signalfilter               import rawprecision
from control.taskio             import ConfigTrackIO
from control.processor          import processors
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import (FitToHairpinTask, FitToHairpinProcessor,
                                        FitBead, Distance)

from view.base                  import enableOnTrack
from view.plots                 import (PlotView, PlotAttrs, from_py_func,
                                        DpxNumberFormatter, WidgetCreator, DpxKeyedRow)
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
        task = obj.defaultidenfication()
        if task is None:
            obj.identification.remove()
        else:
            obj.identification.update(**task.config())
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
        cls.stretch     .setdefault(self, 1./8.8e-4) # type: ignore
        cls.bias        .setdefault(self, None)   # type: ignore

    sequencekey  = SequenceKeyProp()
    sequencepath = SequenceProp[Optional[str]]('last.path.sequence')
    oligos       = SequenceProp[Optional[Sequence[str]]]('oligos')
    stretch      = FitParamProp('stretch')
    bias         = FitParamProp('bias')

    @property
    def defaultidenfication(self):
        "returns the default identification task"
        ols = self.oligos
        seq = self.sequencepath
        if ols is None or len(ols) == 0 or len(readsequence(seq)) == 0:
            return None
        else:
            return FitToHairpinTask.read(seq, ols)

    @property
    def distances(self) -> Dict[str, Distance]:
        "returns the distances which were computed"
        return self.fits.distances if self.fits is not None else {}

    def __set_ids_and_distances(self, peaks):
        task = self.identification.task
        dico = self.peaks
        if task is None:
            dico['bases'] = (dico['z']-self.bias)*self.stretch
            return

        nan       = lambda: np.full((len(peaks),), np.NaN, dtype = 'f4')
        cnf       = task.config()
        self.fits = FitToHairpinProcessor.compute((self.bead, peaks), **cnf)[1]

        for name in readsequence(self.sequencepath):
            dist = self.distances[name].stretch, self.distances[name].bias

            dico[name+'bases']          = (dico['z'] - dist[1])*dist[0]

            tmp                         = task.peakids[name](dico['z'], *dist)['key']
            good                        = tmp >= 0

            dico[name+'id']             = nan()
            dico[name+'id']      [good] = tmp[good]

            dico[name+'distance']       = nan()
            dico[name+'distance'][good] = (tmp - dico[name+'bases'])[good]

        dico['bases']    = dico[self.sequencekey+'bases']
        dico['id']       = dico[self.sequencekey+'id']
        dico['distance'] = dico[self.sequencekey+'distance']

    def __set_probas(self, peaks):
        task = self.eventdetection.task
        prob = Probability(framerate   = self.track.framerate,
                           minduration = task.events.select.minduration)
        dur  = self.track.phaseduration(..., task.phase)
        ncyc = self.track.ncycles
        for i, (_, evts) in enumerate(peaks):
            val                       = prob(evts, dur)
            self.peaks['duration'][i] = val.averageduration
            self.peaks['sigma'][i]    = prob.resolution(evts)
            self.peaks['count'][i]    = min(100., val.nevents / ncyc*100.)

    def setpeaks(self, dtl) -> Optional[FitBead]:
        "sets current bead peaks and computes the fits"
        if dtl is None:
            self.peaks = dict.fromkeys(('z', 'id', 'distance', 'sigma', 'bases',
                                        'duration', 'count'), [])
            self.fits  = None
            return

        nan        = lambda: np.full((len(peaks),), np.NaN, dtype = 'f4')
        peaks      = tuple(self.peakselection.task.details2output(dtl))
        self.peaks = dict(z        = np.array([i for i, _ in peaks], dtype = 'f4'),
                          sigma    = nan(),
                          duration = nan(),
                          count    = nan())

        self.estimatedbias  = self.peaks['z'][0]

        self.__set_ids_and_distances(peaks)
        self.__set_probas(peaks)

        return self.peaks

    def runbead(self):
        "returns a tuple (dataitem, bead) to be displayed"
        if self.track is None:
            return None

        root  = self.roottask
        ibead = self.bead
        task  = self.eventdetection.task
        if task is None:
            task  = self.config.tasks.eventdetection.get()
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
        super().reset(biases    = {i: j.bias    for i, j in dist.items()},
                      stretches = {i: j.stretch for i, j in dist.items()})

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
            bases.start  = (yrng.start - hvr.bias)*hvr.stretch
            bases.end    = (yrng.end   - hvr.bias)*hvr.stretch

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
        if len(self._model.distances):
            fcn  = lambda i: self._model.distances[i].value
            return sorted(lst, key = fcn)
        else:
            return super()._sort(lst)

    def callbacks(self,                     # pylint: disable=arguments-differ
                  hover: SequenceHoverMixin,
                  tick1: SequenceTicker,
                  div:   'PeaksStatsDiv',
                  peaksrc: ColumnDataSource):
        "sets-up callbacks for the tooltips and grids"
        widget = super().callbacks(hover, tick1)
        source = hover.source

        @from_py_func
        def _js_cb(cb_obj = None,
                   hvr    = hover,
                   src    = source,
                   peaks  = peaksrc,
                   stats  = div):
            if cb_obj.value in src.column_names:
                hvr.bias    = hvr.biases [cb_obj.value]
                hvr.stretch = hvr.stretch[cb_obj.value]
                peaks.data['id']       = peaks.data[cb_obj.value+'id']
                peaks.data['bases']    = peaks.data[cb_obj.value+'bases']
                peaks.data['distance'] = peaks.data[cb_obj.value+'distance']
                stats.text             = stats.data[cb_obj.value]
                hvr.updating = 'seq'
                hvr.updating = ''
        widget.js_on_change('value', _js_cb)

class PeaksStatsDiv(Div): # pylint: disable = too-many-ancestors
    "div for displaying stats"
    data               = props.Dict(props.String, props.String)
    __implementation__ = """
        import {Div, DivView} from "models/widgets/div"
        import * as p from "core/properties"

        export class PeaksStatsDiv extends Div
          type: "PeaksStatsDiv"
          default_view: DivView

          @define {
            data: [ p.Any,  {}]
          }
    """

class PeaksStatsWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[PeaksStatsDiv]
        css = self.css.stats
        css.defaults = {'title.format': '{}',
                        'lines': [['css:title.stretch',    '.4f'],
                                  ['css:title.bias',       '.4f'],
                                  [u'σ[HF] (µm)',         '.4f'],
                                  [u'σ[Peaks] (µm)',      '.4f'],
                                  [u'Peak count',         '.0f'],
                                  [u'Identified peaks',   '.0f'],
                                  [u'Unknown peaks',      '.0f']]}

    def create(self, _) -> List[Widget]:
        self.__widget = PeaksStatsDiv()
        self.reset()
        return [self.__widget]

    def reset(self):
        data = self.__data()
        if len(data) == 1:
            self.__widget.text = next(iter(data.values()))
        else:
            self.__widget.text = data[self._model.sequencekey]
        self.__widget.data = data

    def __data(self) -> Dict[str,str]:
        get    = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        titles = [(get(i[0]), i[1]) for i in self.css.stats.lines.get()]
        values = ['']*len(titles) # type: List

        if self._model.track is not None:
            values[0] = self._model.stretch
            values[1] = self._model.bias
            values[2] = rawprecision(self._model.track, self._model.bead)
            values[3] = np.mean(self._model.peaks['sigma'])
            values[4] = len(self._model.peaks['z'])

        line = '<tr><td>'+self.css.stats.title.format.get()+'</td><td>{}</td></tr>'
        fcn  = lambda fmt, val: '' if val == '' else ('{:'+fmt+'}').format(val)
        tab  = lambda: ('<table>'
                        + ''.join(line.format(i[0], fcn(i[1], j))
                                  for i, j in zip(titles, values))
                        +'</table>')

        if self._model.identification.task is not None:
            ret = dict()
            for key in readsequence(self._model.sequencepath):
                values[5] = np.isfinite(self._model.peaks[key+'id']).sum()
                values[6] = (len(self._model.identification.task.peakids[key].peaks)-1
                             -values[5])
                ret[key] = tab()
            return ret
        else:
            return {'': tab()}

class PeakListWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DataTable]
        css           = self.css.peaks.columns
        css.default   = [['z',          'css:ylabel',    '0.0000'],
                         ['bases',      u'Z (base)',     '0.0'],
                         ['id',         u'Id',           '0'],
                         ['distance',   u'Distance',     '0.0'],
                         ['count',      'css:xlabel',    '0.0'],
                         ['duration',   'css:xtoplabel', '0.000'],
                         ['sigma',      u'σ (µm)',       '0.0000']]

    def create(self, _) -> List[Widget]:
        width = self.cssroot.input.width.get()
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        cols  = list(TableColumn(field     = i[0],
                                 title     = get(i[1]),
                                 formatter = DpxNumberFormatter(format = i[2]))
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

    @property
    def model(self):
        "returns the model"
        return self._model

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
        self._fig = figure(**self._figargs(y_range = Range1d,
                                           name    = 'Peaks:fig',
                                           x_range = Range1d))
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
        self._widgets['seq'].callbacks(self._hover,
                                       self._ticker,
                                       widgets['stats'][-1],
                                       self._peaksrc)
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
        return layouts.row(lay, DpxKeyedRow(self, self._fig))

    def _reset(self, _):
        data, peaks        = self.__data()
        self._peaksrc.update(data = peaks, column_names = list(peaks.keys()))
        self._histsrc.data = data
        self._hover .reset()
        self._ticker.reset()
        for widget in self._widgets.values():
            widget.reset()

        self.setbounds(self._fig.y_range, 'y', data['z'][[0,-1]])
        self._hover.slaveaxes(self._fig, self._peaksrc, inpy = True)

class PeaksConfigTrackIO(ConfigTrackIO):
    "selects the default tasks"
    def __init__(self, model):
        tasks         = model.config.tasks
        tasks.default = ['extremumalignment', 'eventdetection', 'peakselector']
        super().__init__(tasks)
        self.__model  = model

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file and adds a alignment"
        items = super().open(path, model)
        if items is not None:
            task = self.__model.defaultidenfication
            if task is not None:
                items[0] += (task,)
        return items

class PeaksPlotView(PlotView):
    "Peaks plot view"
    PLOTTER = PeaksPlotCreator

    def ismain(self):
        "Alignment, ... is set-up by default"
        PeaksConfigTrackIO.setup(self._ctrl, self._plotter.model)

        trk = self._ctrl.getGlobal('project').track
        trk.observe(lambda itm: self._ctrl.clearData(itm.old))
