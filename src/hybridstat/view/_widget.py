#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import List, Dict, Any
from pathlib                    import Path
import os

import bokeh.core.properties as props
from bokeh.models               import (DataTable, TableColumn, CustomJS,
                                        Widget, Div, StringFormatter, Paragraph,
                                        Dropdown)

import numpy                    as     np

from signalfilter               import rawprecision

from peakcalling.tohairpin      import PeakGridFit, ChiSquareFit

from utils.gui                  import startfile
from excelreports.creation      import writecolumns
from view.dialog                import FileDialog
from view.pathinput             import PathInput
from view.plots                 import DpxNumberFormatter, WidgetCreator
from view.toolbar               import FileListMixin
from sequences.view             import (SequenceTicker, SequenceHoverMixin,
                                        OligoListWidget, SequencePathWidget)
from modaldialog.view           import AdvancedTaskMixin, T_BODY
from ._model                    import PeaksPlotModelAccess

class ReferenceWidget(WidgetCreator[PeaksPlotModelAccess], FileListMixin):
    "Dropdown for choosing the reference"
    def __init__(self, model) -> None:
        super().__init__(model)
        FileListMixin.__init__(self)
        self.__widget: Dropdown  = None
        self.css.title.reference.default      = 'Reference Track'
        self.css.title.reference.none.default = 'None'

    def create(self, action, *_) -> List[Widget]:
        "creates the widget"
        self.__widget = Dropdown(name  = 'HS:Sequence',
                                 width = self.css.input.width.get(),
                                 **self.__data())
        @action
        def _py_cb(new):
            inew = int(new)
            val  = None if inew < 0 else [i for _, i in self.files][inew]
            self._model.fittoreference.reference = val

        self.__widget.on_click(_py_cb)
        return [Paragraph(text = self.css.title.reference.get()), self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

    @property
    def widget(self):
        "returns the widget"
        return self.__widget

    def __data(self) -> dict:
        lst   = list(self.files)
        menu  = [(j, str(i)) for i, j in enumerate(i for i, _ in lst)]
        menu += [None, (self.css.title.reference.none.get(), '-1')]

        key   = self._model.fittoreference.reference
        index = -1 if key is None else [i for _, i in lst].index(key)
        return dict(menu  = menu, label = menu[index][0], value = str(index))

class PeaksOligoListWidget(OligoListWidget):
    "deals with oligos"
    def create(self, action, *_) -> List[Widget]: # pylint: disable=arguments-differ
        "creates the widget"
        return super().create(action)

class PeaksSequencePathWidget(SequencePathWidget):
    "Widget for setting the sequence to use"
    def _sort(self, lst) -> List[str]: # type: ignore
        dist = self._model.distances
        if len(dist):
            lst  = [i for i in lst if i in dist]
            return sorted(lst, key = lambda i: dist[i].value)
        return super()._sort(lst)

    def create(self, action, *_) -> List[Widget]: # pylint: disable=arguments-differ
        "creates the widget"
        return super().create(action)

    def callbacks(self,             # type: ignore # pylint: disable=arguments-differ
                  hover: SequenceHoverMixin,
                  tick1: SequenceTicker,
                  div:   'PeaksStatsDiv',
                  table: DataTable):
        "sets-up callbacks for the tooltips and grids"
        code = "hvr.on_change_sequence(src, peaks, stats, tick1, tick2, cb_obj)"
        args = dict(hvr   = hover, src   = hover.source, peaks = table,
                    stats = div,   tick1 = tick1,        tick2 = tick1.axis)
        self.widget.js_on_change('value', CustomJS(code = code, args = args))

class PeaksStatsDiv(Div): # pylint: disable = too-many-ancestors
    "div for displaying stats"
    data               = props.Dict(props.String, props.String)
    __implementation__ = "peakstats.coffee"

class PeaksStatsWidget(WidgetCreator[PeaksPlotModelAccess]):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget: PeaksStatsDiv = None
        css = self.css.stats
        css.defaults = {'title.format': '{}',
                        'title.openhairpin': u' & open hairpin',
                        'title.orientation': u'-+ ',
                        'lines': [['css:title.stretch', '.3f'],
                                  ['css:title.bias',    '.4f'],
                                  [u'σ[HF] (µm)',       '.4f'],
                                  [u'σ[Peaks] (µm)',    '.4f'],
                                  [u'Average Skew ',    '.2f'],
                                  [u'Peak count',       '.0f'],
                                  [u'Events per Cycle', '.1f'],
                                  [u'Down Time Φ₅ (s)', '.1f'],
                                  [u'Sites found',      ''],
                                  [u'Silhouette',       '.1f'],
                                  [u'reduced χ²',       '.1f']]}

    def create(self, *_) -> List[Widget]: # pylint: disable=arguments-differ
        "creates the widget"
        self.__widget = PeaksStatsDiv()
        self.reset(None)
        return [self.__widget]

    def reset(self, resets):
        "resets the widget upon opening a new file, ..."
        itm  = self.__widget if resets is None else resets[self.__widget]
        data = self.__data()
        itm.update(data = data, text = data.get(self._model.sequencekey, data['']))

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

            self.values[2] = rawprecision(mdl.track, mdl.bead)
            if len(mdl.peaks['z']):
                self.values[3] = mdl.peaks['sigma']
            self.values[4] = mdl.peaks['skew']
            self.values[5] = max(0, len(mdl.peaks['z']) - 1)
            self.values[6] = 0.     if self.values[5] < 1 else mdl.peaks['count'][1:]/100.
            self.values[7] = np.NaN if self.values[5] < 1 else mdl.peaks['duration'][0]

        def sequencedependant(self, mdl, dist, key):
            "all sequence dependant stats"
            self.values[0] = dist[key].stretch
            self.values[1] = dist[key].bias

            task      = mdl.identification.task
            tmp       = task.match[key].peaks
            if len(tmp):
                remove = task.match[key].peaks[[0,-1]]
                nrem   = sum(i in remove for i in mdl.peaks[key+'id'])
            else:
                nrem   = 0
            nfound    = np.isfinite(mdl.peaks[key+'id']).sum()-nrem
            npks      = len(task.match[key].hybridisations)
            self.values[8] = '{}/{}'.format(nfound, npks)
            if nrem == 2:
                self.values[8] += self.openhp

            self.values[9] = PeakGridFit.silhouette(dist, key)

            if nfound > 2:
                stretch         = dist[key].stretch
                self.values[10] = (np.nanstd(mdl.peaks[key+'distance'])
                                   / ((np.mean(self.values[3]*stretch))**2
                                      * (nfound - 2)))

        def referencedependant(self, mdl):
            "all sequence dependant stats"
            fittoref       = mdl.fittoreference
            self.values[0] = fittoref.stretch
            self.values[1] = fittoref.bias

            nfound    = np.isfinite(mdl.peaks['id']).sum()
            npks      = fittoref.ref
            self.values[8] = '{}/{}'.format(nfound, npks)
            if nrem == 2:
                self.values[10] = (np.nanstd(mdl.peaks['distance'])
                                   / ((np.mean(self.values[3]))**2
                                      * (nfound - 2)))

        def __call__(self) -> str:
            return ('<table>'
                    + ''.join(self.line.format(i[0], self.__fmt(i[1], j))
                              for i, j in zip(self.titles, self.values))
                    +'</table>')

        @staticmethod
        def __fmt(fmt, val):
            if isinstance(val, str):
                return val

            if np.isscalar(val):
                return ('{:'+fmt+'}').format(val)

            if isinstance(val, (list, np.ndarray)):
                if len(val) == 0:
                    return '0 ± ∞'
                val = np.mean(val), np.std(val)
            return ('{:'+fmt+'} ± {:'+fmt+'}').format(*val)

    def __data(self) -> Dict[str,str]:
        tab = self._TableConstructor(self.css)
        tab.trackdependant(self._model)
        ret = {'': tab()}

        if self._model.identification.task is not None:
            dist = self._model.distances
            for key in dist:
                tab.sequencedependant(self._model, dist, key)
                ret[key] = tab()

        elif self._model.fittoreference.task is not None:
            tab.referencedependant(self._model)
            ret[''] = tab()
        return ret

class PeakListWidget(WidgetCreator[PeaksPlotModelAccess]):
    "Table containing stats per peaks"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.__widget: DataTable      = None
        self.css.peaks.height.default = 400
        self.css.peaks.table.error.default = ('File extension must be .xlsx',
                                              'warning')
        css               = self.css.peaks.columns
        css.width.default = 60
        css.refid.default = '0.0000'
        css.default       = [['z',        'css:ylabel',    '0.0000'],
                             ['bases',    u'Z (base)',     '0.0'],
                             ['id',       u'Id',           '0'],
                             ['orient',   u'Strand',       ''],
                             ['distance', u'Distance',     '0.0'],
                             ['count',    'css:xlabel',    '0.0'],
                             ['duration', 'css:xtoplabel', '0.000'],
                             ['sigma',    u'σ (µm)',       '0.0000'],
                             ['skew',     u'skew',         '0.00']]

    def __cols(self):
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        fmt   = lambda i: (StringFormatter(text_align = 'center',
                                           font_style = 'bold') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = get(i[1]),
                                 formatter  = fmt(i[2]))
                     for i in self.css.peaks.columns.get())

        cnf   = self.css.peaks
        isref = (self._model.fittoreference.task is not None and
                 self._model.identification.task is None)
        for name in ('id', 'distance'):
            ind = next(i for i, j in enumerate(cnf.columns.get()) if j[0] == name)
            fmt = cnf.columns.refid.get() if isref else cnf.columns.get()[ind][-1]
            cols[ind].formatter.format = fmt
        return cols

    def create(self, _, src) -> List[Widget]: # type: ignore # pylint: disable=arguments-differ
        "creates the widget"
        width = self.css.peaks.columns.width.get()
        cols  = self.__cols()
        self.__widget = DataTable(source      = src,
                                  columns     = cols,
                                  editable    = False,
                                  row_headers = False,
                                  width       = width*len(cols),
                                  height      = self.css.peaks.height.get(),
                                  name        = "Peaks:List")
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        # bug in bokeh 0.12.9: table update is incorrect unless the number
        # of rows is fixed
        height = self.css.peaks.height.get()
        if height == self.__widget.height:
            height = height+1
        resets[self.__widget].update(height = height, columns = self.__cols())

class PeakIDPathWidget(WidgetCreator[PeaksPlotModelAccess]):
    "Selects an id file"
    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        self.keeplistening       = True
        self.__widget: PathInput = None
        self.__dlg    = FileDialog(config    = self._ctrl,
                                   storage   = 'constraints.path',
                                   filetypes = '*|xlsx')

        css          = self.css.constraints
        css.defaults = {'title': u'Id file path', 'filechecks': 500}

    def listentofile(self, doc, action):
        "sets-up a periodic callback which checks whether the id file has changed"
        finfo = [None, None]

        @action
        def _do_resetmodel():
            self._model.identification.resetmodel(self._model)

        def _callback():
            if not self.keeplistening:
                return

            path = self._model.constraintspath
            if path is None:
                finfo[0] = None
                return

            new  = finfo[0] is None
            time = os.path.getmtime(path) if Path(path).exists() else 0
            diff = time != finfo[1]

            finfo[1] = time # type: ignore
            if new:
                finfo[0] = path
                return

            if not diff:
                return

            _do_resetmodel()

        doc.add_periodic_callback(_callback, self.css.constraints.filechecks.get())

    def create(self, action, _) -> List[Widget]: # type: ignore # pylint: disable=arguments-differ
        "creates the widget"
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
                if not path.endswith(".xlsx"):
                    raise IOError(*self.css.peaks.table.error.get())
                try:
                    writecolumns(path, "Summary",
                                 [('Bead', [self._model.bead]),
                                  ('Reference', [self._model.sequencekey]),
                                  ('Stretch (base/µm)', [self._model.stretch]),
                                  ('Bias (µm)', [self._model.bias])])
                except:
                    raise
                else:
                    startfile(path)

            self._model.constraintspath = str(Path(path).resolve())

        self.__widget.on_change('click', _onclick_cb)
        self.__widget.on_change('value', _onchangetext_cb)

        self.__dlg.title = title
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened, ..."
        txt  = ''
        path = self._model.constraintspath
        if path is not None and Path(path).exists():
            txt = str(Path(path).resolve())
        (self.__widget if resets is None else resets[self.__widget]).update(value = txt)

class AdvancedWidget(WidgetCreator[PeaksPlotModelAccess], AdvancedTaskMixin):
    "access to the modal dialog"
    _TITLE        = 'Hybridstat Configuration'
    _BODY: T_BODY = (('Minimum frame count per event',    '%(_framecount)d'),
                     ('Minimum event count per peak',     '%(_eventcount)d'),
                     ('Align cycles using peaks',         '%(_align5)b'),
                     ('Peak kernel size (blank ⇒ auto)',  '%(_precision)of'),
                     ('Exhaustive fit algorithm',         '%(_fittype)b'),
                     ('Use a theoretical peak 0 in fits', '%(_peak0)b'),
                     ('Max distance to theoretical peak', '%(_dist2theo)d'),

                    )

    def __init__(self, model:PeaksPlotModelAccess) -> None:
        super().__init__(model)
        AdvancedTaskMixin.__init__(self)
        self._outp: Dict[str, Dict[str, Any]] = {}

    def reset(self, resets):
        "resets the wiget when a new file is opened, ..."
        AdvancedTaskMixin.reset(resets)

    def create(self, action, _) -> List[Widget]: # pylint: disable=arguments-differ
        "creates the widget"
        return AdvancedTaskMixin.create(self, action)

    _framecount = AdvancedTaskMixin.attr('eventdetection.events.select.minlength')
    _eventcount = AdvancedTaskMixin.attr('peakselection.group.mincount')
    _align5     = AdvancedTaskMixin.none('peakselection.align')
    _precision  = AdvancedTaskMixin.attr('peakselection.precision')

    @property
    def _peak0(self) -> bool:
        return self._model.identification.default('fit').firstpeak

    @_peak0.setter
    def _peak0(self, value):
        if value == self._peak0:
            return

        self._model.identification.updatedefault('fit', firstpeak = value)
        self._model.identification.resetmodel(self._model)

    @property
    def _fittype(self) -> bool:
        return isinstance(self._model.identification.default('fit'), PeakGridFit)

    @_fittype.setter
    def _fittype(self, value):
        if value == self._fittype:
            return

        inst = (ChiSquareFit, PeakGridFit)[value]()
        self._model.identification.updatedefault('fit', inst)
        self._model.identification.resetmodel(self._model)

    @property
    def _dist2theo(self) -> int:
        return self._model.identification.default('match').window

    @_dist2theo.setter
    def _dist2theo(self, value:int):
        if value == self._dist2theo:
            return
        self._model.identification.updatedefault('match', window = value)
        self._model.identification.resetmodel(self._model)

def createwidgets(mdl: PeaksPlotModelAccess) -> Dict[str, WidgetCreator]:
    "returns a dictionnary of widgets"
    return dict(seq      = PeaksSequencePathWidget(mdl),
                ref      = ReferenceWidget(mdl),
                oligos   = PeaksOligoListWidget(mdl),
                stats    = PeaksStatsWidget(mdl),
                peaks    = PeakListWidget(mdl),
                cstrpath = PeakIDPathWidget(mdl),
                advanced = AdvancedWidget(mdl))
