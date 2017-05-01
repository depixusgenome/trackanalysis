#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional, Sequence, Tuple, List, Dict,
                                        Union, TYPE_CHECKING)
from itertools                  import product
from pathlib                    import Path

import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.plotting             import figure, Figure    # pylint: disable=unused-import
from bokeh.models               import (LinearAxis, Range1d, ColumnDataSource,
                                        DataTable, TableColumn, Model, Widget,
                                        Div, StringFormatter, TapTool, CustomJS)

import numpy                    as     np

import sequences
from signalfilter               import rawprecision
from control.taskio             import ConfigTrackIO, ConfigGrFilesIO
from control.processor          import processors
from eventdetection.processor   import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import (FitToHairpinTask, FitToHairpinProcessor,
                                        FitBead, Distance, HairpinDistance)

from view.base                  import enableOnTrack
from view.dialog                import FileDialog
from view.intinput              import PathInput
from view.plots                 import (PlotView, PlotAttrs, from_py_func,
                                        DpxNumberFormatter, WidgetCreator,
                                        DpxKeyedRow, PlotState)
from view.plots.tasks           import (TaskPlotModelAccess, TaskPlotCreator,
                                        TaskAccess)
from view.plots.sequence        import (readsequence, SequenceTicker, OligoListWidget,
                                        SequenceHoverMixin, SequencePathWidget,
                                        FitParamProp    as _FitParamProp,
                                        SequenceKeyProp as _SequenceKeyProp)

from ..probabilities            import Probability
from ..processor                import fittohairpintask

class FitToHairpinAccess(TaskAccess):
    "access to the FitToHairpinTask"
    def __init__(self, ctrl):
        super().__init__(ctrl, FitToHairpinTask)

    @staticmethod
    def _configattributes(kwa):
        return {}

class FitParamProp(_FitParamProp):
    "access to bias or stretch"
    def __get__(self, obj, tpe) -> Optional[str]:
        if obj is not None:
            dist = obj.distances.get(obj.sequencekey, None)
            if dist is not None:
                return getattr(dist, self._key)

        return super().__get__(obj, tpe)

class SequenceKeyProp(_SequenceKeyProp):
    "access to the sequence key"
    def __get__(self, obj, tpe) -> Optional[str]:
        "returns the current sequence key"
        if obj is not None and len(obj.distances) and self.fromglobals(obj) is None:
            if len(obj.distances):
                return min(obj.distances, key = obj.distances.__getitem__)
        return super().__get__(obj, tpe)

class _PeaksPlotModelAccess(TaskPlotModelAccess):
    "Access to identification"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        self.identification = FitToHairpinAccess(self)

        cls = type(self)
        cls.sequencepath    .setdefault(self, None)
        cls.oligos          .setdefault(self, [], size = 4)
        cls.constraintspath .setdefault(self, None)
        cls.useparams       .setdefault(self, True)

    props           = TaskPlotModelAccess.props
    sequencepath    = props.configroot[Optional[str]]('last.path.sequence')
    oligos          = props.configroot[Optional[Sequence[str]]]('oligos')
    constraintspath = props.projectroot[Optional[str]]('constraints.path')
    useparams       = props.projectroot[bool]('constraints.useparams')

    @property
    def defaultidenfication(self):
        "returns the default identification task"
        ols = self.oligos
        seq = self.sequencepath
        if ols is None or len(ols) == 0 or len(readsequence(seq)) == 0:
            return None
        else:
            return fittohairpintask(seq, ols, self.constraintspath, self.useparams)

class PeaksPlotModelAccess(_PeaksPlotModelAccess):
    "Access to peaks"
    def __init__(self, ctrl, key: Optional[str] = None) -> None:
        super().__init__(ctrl, key)
        self.config.root.tasks.extremumalignment.default = ExtremumAlignmentTask()

        self.eventdetection     = TaskAccess(self, EventDetectionTask)
        self.peakselection      = TaskAccess(self, PeakSelectorTask)
        self.fits               = None   # type: Optional[FitBead]
        self.peaks              = dict() # type: Dict[str, np.ndarray]
        self.estimatedbias      = 0.

        cls = type(self)
        cls.sequencekey .setdefault(self, None) # type: ignore
        cls.stretch     .setdefault(self)       # type: ignore
        cls.bias        .setdefault(self)       # type: ignore

    sequencekey  = SequenceKeyProp()
    stretch      = FitParamProp('stretch')
    bias         = FitParamProp('bias')

    @property
    def distances(self) -> Dict[str, Distance]:
        "returns the distances which were computed"
        return self.fits.distances if self.fits is not None else {}

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
        if self.track is None or self.checkbead(False):
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

    def reset(self) -> bool:
        "adds tasks if needed"
        if self.track is None or self.checkbead(False):
            return True

        if self.eventdetection.task is None:
            self.eventdetection.update()

        if self.peakselection.task is None:
            self.peakselection.update()

        task = self.defaultidenfication
        cur  = self.identification.task
        if task is None and cur is not None:
            self.identification.remove()
        elif task is not None and cur is None:
            self.identification.update(**task.config())
        return False


    def __set_ids_and_distances(self, peaks):
        task  = self.identification.task
        dico  = self.peaks
        names = 'bases', 'id', 'distance', 'orient'
        nan   = np.full((len(peaks),), np.NaN, dtype = 'f4')

        dico.update(**dict.fromkeys(names, nan))
        dico['orient'] = np.array([' '] * len(nan))

        if task is None:
            dico['bases']  = (dico['z']-self.bias)*self.stretch
            return

        self.fits = FitToHairpinProcessor.compute((self.bead, peaks),
                                                  **task.config())[1]

        for key in product(readsequence(self.sequencepath), names):
            dico[''.join(key)] = np.copy(dico[key[1]])

        strori  = self.css.stats.title.orientation.get()
        alldist = self.distances
        for key, seq in readsequence(self.sequencepath).items():
            if key not in alldist:
                continue

            dist = alldist[key].stretch, alldist[key].bias
            tmp  = task.peakids[key](dico['z'], *dist)['key']
            good = tmp >= 0
            ori  = dict(sequences.peaks(seq, self.oligos))

            dico[key+'bases']          = (dico['z'] - dist[1])*dist[0]
            dico[key+'id']      [good] = tmp[good]
            dico[key+'distance'][good] = (tmp - dico[key+'bases'])[good]
            dico[key+'orient']  [good] = [strori[ori.get(int(i+0.01), 2)]
                                          for i in dico[key+'id'][good]]

        for key in names:
            dico[key] = dico[self.sequencekey+key]

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


    def create(self, fig, *args, **kwa):
        "Creates the hover tool for histograms"
        super().create(fig, *args, **kwa)
        jsc = CustomJS(args = {'fig': fig, 'source': self.source},
                       code = 'cb_obj.apply_update(fig, source)')
        self.js_on_change("updating", jsc)

    def reset(self, resets):
        "Creates the hover tool for histograms"
        dist = self._model.distances
        super().reset(resets,
                      biases    = {i: j.bias    for i, j in dist.items()},
                      stretches = {i: j.stretch for i, j in dist.items()})

    def pyslaveaxes(self, fig, src, resets): # pylint: disable=arguments-differ
        "slaves a histogram's axes to its y-axis"
        yrng         = fig.y_range
        bases        = fig.extra_y_ranges['bases']
        resets[bases].update(start  = (yrng.start - self._model.bias)*self._model.stretch,
                             end    = (yrng.end   - self._model.bias)*self._model.stretch)

        zval = src["z"]
        ix1  = 0
        ix2  = len(zval)
        for i in range(ix2):
            if zval[i] < yrng.start:
                ix1 = i+1
                continue
            if zval[i] > yrng.end:
                ix2 = i
                break

        end = lambda x: (0. if len(zval) < 2 or ix1 == ix2 else max(src[x][ix1:ix2])+1)
        resets[fig.extra_x_ranges['duration']].update(start = 0., end = end('duration'))
        resets[fig.x_range]                   .update(start = 0., end = end('count'))

    def jsslaveaxes(self, fig, src): # pylint: disable=arguments-differ
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

        fig.y_range.callback = from_py_func(_onchangebounds)

class PeaksSequencePathWidget(SequencePathWidget):
    "Widget for setting the sequence to use"
    def _sort(self, lst) -> List[str]:
        dist = self._model.distances
        if len(dist):
            lst  = [i for i in lst if i in dist]
            return sorted(lst, key = lambda i: dist[i].value)
        else:
            return super()._sort(lst)

    def callbacks(self,                     # pylint: disable=arguments-differ
                  hover: SequenceHoverMixin,
                  tick1: SequenceTicker,
                  div:   'PeaksStatsDiv',
                  table: DataTable):
        "sets-up callbacks for the tooltips and grids"
        widget = self.widget
        source = hover.source
        tick2  = tick1.axis

        @from_py_func
        def _js_cb(hvr    = hover,  # pylint: disable=too-many-arguments
                   src    = source,
                   peaks  = table,
                   stats  = div,
                   tick1  = tick1,
                   tick2  = tick2,
                   cb_obj = None):
            if cb_obj.value in src.column_names:
                cb_obj.label     = cb_obj.value
                tick1.key        = cb_obj.value
                tick2.key        = cb_obj.value
                src.data['text'] = src.data[cb_obj.value]
                src.trigger("change")

                if cb_obj.value in stats.data:
                    stats.text   = stats.data   [cb_obj.value]

                if cb_obj.value+'id' in peaks.source.column_names:
                    for key in ('id', 'bases', 'distance', 'orient'):
                        ref = cb_obj.value+key
                        peaks.source.data[key] = peaks.source.data[ref]
                    peaks.trigger("change")

                if cb_obj.value in hvr.stretches:
                    hvr.updating = 'seq'
                    hvr.stretch  = hvr.stretches[cb_obj.value]
                    hvr.bias     = hvr.biases   [cb_obj.value]
                    hvr.updating = '*'
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
                        'title.openhairpin': u' & open hairpin',
                        'title.orientation': u'-+ ',
                        'lines': [['css:title.stretch', '.4f'],
                                  ['css:title.bias',    '.4f'],
                                  [u'σ[HF] (µm)',       '.4f'],
                                  [u'σ[Peaks] (µm)',    '.4f'],
                                  [u'Peak count',       '.0f'],
                                  [u'Sites found',      ''],
                                  [u'Silhouette',       '.1f'],
                                  [u'reduced χ²',       '.1f']]}

    def create(self, _) -> List[Widget]:
        self.__widget = PeaksStatsDiv(width = self.css.input.width.get())
        self.reset(None)
        return [self.__widget]

    def reset(self, resets):
        data = self.__data()
        if len(data) == 1:
            txt = next(iter(data.values()))
        else:
            txt = data[self._model.sequencekey]
        if resets is None:
            self.__widget.update(data = data, text = txt)
        else:
            resets[self.__widget].update(data = data, text = txt)


    class _TableConstructor:
        "creates the html table containing stats"
        def __init__(self, css):
            get         = lambda i: css[i[4:]].get() if i.startswith('css:') else i
            self.titles = [(get(i[0]), i[1]) for i in css.stats.lines.get()]
            self.values = ['']*len(self.titles) # type: List
            self.line   = '<tr><td>'+css.stats.title.format.get()+'</td><td>{}</td></tr>'
            self.openhp = css.stats.title.openhairpin.get()

        def trackdependant(self, mdl):
            "all track dependant stats"
            if mdl.track is None:
                return

            self.values[0] = mdl.stretch
            self.values[1] = mdl.bias
            self.values[2] = rawprecision(mdl.track, mdl.bead)
            if len(mdl.peaks['z']):
                self.values[3] = np.mean(mdl.peaks['sigma'])
            self.values[4] = max(0, len(mdl.peaks['z']) - 1)

        def sequencedependant(self, mdl, dist, key):
            "all sequence dependant stats"
            task      = mdl.identification.task
            remove    = task.peakids[key].peaks[[0,-1]]
            nrem      = sum(i in remove for i in mdl.peaks[key+'id'])
            nfound    = np.isfinite(mdl.peaks[key+'id']).sum()-nrem
            npks      = len(task.peakids[key].hybridizations)
            self.values[5] = '{}/{}'.format(nfound, npks)
            if nrem == 2:
                self.values[5] += self.openhp

            self.values[6] = HairpinDistance.silhouette(dist, key)

            if nfound > 2:
                stretch        = dist[key].stretch
                self.values[7] = (np.nanstd(mdl.peaks[key+'id'])
                                  / ((self.values[3]*stretch)**2 * (nfound - 2)))

        def __call__(self) -> str:
            return ('<table>'
                    + ''.join(self.line.format(i[0], self.__fmt(i[1], j))
                              for i, j in zip(self.titles, self.values))
                    +'</table>')

        @staticmethod
        def __fmt(fmt, val):
            return val if isinstance(val, str) else ('{:'+fmt+'}').format(val)

    def __data(self) -> Dict[str,str]:
        tab = self._TableConstructor(self.css)
        tab.trackdependant(self._model)

        if self._model.identification.task is not None:
            ret  = dict()
            dist = self._model.distances
            for key in readsequence(self._model.sequencepath):
                if key not in dist:
                    continue

                tab.sequencedependant(self._model, dist, key)
                ret[key] = tab()
            return ret
        else:
            return {'': tab()}

class PeakListWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget     = None # type: Optional[DataTable]
        css               = self.css.peaks.columns
        css.width.default = 65
        css.default       = [['z',        'css:ylabel',    '0.0000'],
                             ['bases',    u'Z (base)',     '0.0'],
                             ['id',       u'Id',           '0'],
                             ['orient',   u'Orientation',  ''],
                             ['distance', u'Distance',     '0.0'],
                             ['count',    'css:xlabel',    '0.0'],
                             ['duration', 'css:xtoplabel', '0.000'],
                             ['sigma',    u'σ (µm)',       '0.0000']]

    def create(self, _) -> List[Widget]:
        width = self.css.peaks.columns.width.get()
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        fmt   = lambda i: (StringFormatter(text_align = 'center',
                                           font_style = 'bold') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = get(i[1]),
                                 formatter  = fmt(i[2]))
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

    def reset(self, resets):
        pass

class PeakIDPathWidget(WidgetCreator):
    "Selects an id file"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[PathInput]
        self.__dlg    = FileDialog(config    = self._ctrl,
                                   storage   = 'constraints.path',
                                   filetypes = '*|xls')

        css          = self.css.constraints
        css.defaults = {'title': u'Id file path'}

    def create(self, action) -> List[Widget]:
        title         = self.css.constraints.title.get()
        width         = self.css.input.width.get() - 10
        self.__widget = PathInput(width = width, title = title,
                                  placeholder = "", value = "",
                                  name = 'Peaks:IDPath')

        @action
        def _onclick_cb(attr, old, new):
            path = self.__dlg.open()
            if path is not None:
                self.__widget.value = str(Path(path).resolve())

        @action
        def _onchangetext_cb(attr, old, new):
            path = self.__widget.value.strip()
            if path == '':
                self._model.constraintspath = None

            elif not Path(path).exists():
                self.reset(None)

            else:
                self._model.constraintspath = str(Path(path).resolve())

        self.__widget.on_change('click', _onclick_cb)
        self.__widget.on_change('value', _onchangetext_cb)

        self.__dlg.title = title
        return [self.__widget]

    def reset(self, resets):
        txt  = ''
        path = self._model.constraintspath
        if path is not None and Path(path).exists():
            txt = str(Path(path).resolve())
        (self.__widget if resets is None else resets[self.__widget]).update(value = txt)

class PeaksPlotCreator(TaskPlotCreator):
    "Creates plots for peaks"
    _MODEL = PeaksPlotModelAccess
    def __init__(self, *args):
        super().__init__(*args)
        self.css.defaults = {'count'           : PlotAttrs('lightblue', 'line', 1),
                             'figure.width'    : 500,
                             'figure.height'   : 800,
                             'xtoplabel'       : u'Duration (s)',
                             'xlabel'          : u'Rate (%)',
                             'widgets.border'  : 10}
        self.css.peaks.defaults = {'duration'  : PlotAttrs('gray', 'diamond', 10),
                                   'count'     : PlotAttrs('lightblue', 'square',  10)}
        self.config.defaults = {'tools'      : 'ypan,ybox_zoom,reset,save,dpxhover,tap'}
        PeaksSequenceHover.defaultconfig(self)
        SequenceTicker.defaultconfig(self)

        self._histsrc = None # type: Optional[ColumnDataSource]
        self._peaksrc = None # type: Optional[ColumnDataSource]
        self._fig     = None # type: Optional[Figure]
        self._widgets = dict(seq      = PeaksSequencePathWidget(self._model),
                             oligos   = OligoListWidget(self._model),
                             stats    = PeaksStatsWidget(self._model),
                             peaks    = PeakListWidget(self._model),
                             cstrpath = PeakIDPathWidget(self._model))
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
        data   = dict.fromkeys(('z', 'count'), [0., 1.])
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
        self.__create_fig()
        rends = self.__add_curves()
        self.__setup_tools(doc, rends)
        return layouts.row(self.__setup_widgets(), DpxKeyedRow(self, self._fig))

    def observe(self):
        super().observe()
        def _observe(_):
            if self.state is not PlotState.active:
                return

            task = self._model.defaultidenfication
            if task is None:
                self._model.identification.remove()
            else:
                self._model.identification.update(**task.config())

        self._model.observeprop('oligos', 'sequencepath',
                                'constraintspath', 'useparams',
                                _observe)
        for widget in self._widgets.values():
            widget.observe()

    def _reset(self):
        data, peaks        = self.__data()
        self._bkmodels[self._peaksrc].update(data = peaks, column_names = list(peaks.keys()))
        self._bkmodels[self._histsrc].update(data = data)
        self._hover .reset(self._bkmodels)
        self._ticker.reset(self._bkmodels)
        for widget in self._widgets.values():
            widget.reset(self._bkmodels)

        self.setbounds(self._fig.y_range, 'y', (data['z'][0], data['z'][-1]))
        self._hover.pyslaveaxes(self._fig, peaks, self._bkmodels)

    def __create_fig(self):
        self._fig = figure(**self._figargs(y_range = Range1d,
                                           name    = 'Peaks:fig',
                                           x_range = Range1d))
        self._fig.extra_x_ranges = {"duration": Range1d(start = 0., end = 0.)}
        axis  = LinearAxis(x_range_name          = "duration",
                           axis_label            = self.css.xtoplabel.get(),
                           axis_label_text_color = self.css.peaks.duration.get().color
                          )
        self._fig.xaxis[0].axis_label_text_color = self.css.count.get().color
        self._fig.add_layout(axis, 'above')
        self._addcallbacks(self._fig)

    def __add_curves(self):
        self._histsrc, self._peaksrc = (ColumnDataSource(i) for i in self.__data())

        css   = self.css
        rends = []
        for key in ('count', 'peaks.count', 'peaks.duration'):
            src = self._peaksrc if 'peaks' in key else self._histsrc
            rng = 'duration' if 'duration' in key else None
            val = css[key].addto(self._fig,
                                 y            = 'z',
                                 x            = key.split('.')[-1],
                                 source       = src,
                                 x_range_name = rng)
            if 'peaks' in key:
                rends.append(val)
        return rends

    def __setup_tools(self, doc, rends):
        tool = self._fig.select(TapTool)
        if len(tool) == 1:
            tool[0].renderers = rends[::-1]

        self._hover.create(self._fig, self._model, self)
        doc.add_root(self._hover)
        self._ticker.create(self._fig, self._model, self)
        self._hover.jsslaveaxes(self._fig, self._peaksrc)

    def __setup_widgets(self):
        action  = self.action()
        widgets = {i: j.create(action) for i, j in self._widgets.items()}
        enableOnTrack(self, self._fig, widgets)

        self._widgets['peaks'].setsource(self._peaksrc)
        self._widgets['seq'].callbacks(self._hover,
                                       self._ticker,
                                       widgets['stats'][-1],
                                       widgets['peaks'][-1])

        mode   = self.css.sizing_mode.get()
        border = self.css.widgets.border.get()
        wwidth = self.css.input.width.get()
        twidth = widgets['peaks'][-1].width+border

        # pylint: disable=redefined-variable-type
        lay = layouts.widgetbox(*widgets['seq'],
                                *widgets['oligos'],
                                *widgets['cstrpath'],
                                width       = wwidth+border,
                                sizing_mode = mode)
        lay = layouts.row(lay, layouts.widgetbox(*widgets['stats']),
                          width       = wwidth*2+border,
                          sizing_mode = mode)
        return layouts.column(lay, *widgets['peaks'],
                              sizing_mode = mode,
                              width       = twidth)

class _PeaksIOMixin:
    def __init__(self, ctrl):
        type(self).__bases__ [1].__init__(self, ctrl)
        self.__model = _PeaksPlotModelAccess(ctrl, 'config'+PeaksPlotCreator.key())

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file and adds a alignment"
        # pylint: disable=no-member
        items = type(self).__bases__[1].open(self, path, model) # type: ignore

        if items is not None:
            task = self.__model.defaultidenfication
            if task is not None:
                items[0] += (task,)
        return items

class PeaksConfigTrackIO(_PeaksIOMixin, ConfigTrackIO):
    "selects the default tasks"

class PeaksConfigGRFilesIO(_PeaksIOMixin, ConfigGrFilesIO):
    "selects the default tasks"

class PeaksPlotView(PlotView):
    "Peaks plot view"
    PLOTTER = PeaksPlotCreator

    def ismain(self):
        "Alignment, ... is set-up by default"
        tasks = self._plotter.model.config.root.tasks
        tasks.default = ['extremumalignment', 'eventdetection', 'peakselector']

        vals = (tuple(tasks.io.open.get()[:-2])
                + ('hybridstat.view.peaksplot.PeaksConfigGRFilesIO',
                   'hybridstat.view.peaksplot.PeaksConfigTrackIO'))
        tasks.io.open.default = vals
