#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
from typing                     import (Optional,   # pylint: disable=unused-import
                                        List, Dict, Any, Type)
from pathlib                    import Path

import bokeh.core.properties as props
from bokeh.models               import (ColumnDataSource, DataTable, TableColumn,
                                        Widget, Div, StringFormatter)

import numpy                    as     np

from signalfilter               import rawprecision

from peakcalling.processor      import HairpinDistance

from view.dialog                import FileDialog
from view.intinput              import PathInput
from view.plots                 import from_py_func, DpxNumberFormatter, WidgetCreator
from view.plots.sequence        import (SequenceTicker, SequenceHoverMixin,
                                        SequencePathWidget)
from peakfinding.selector       import PeakSelector # pylint: disable=unused-import
from modaldialog.view           import AdvancedTaskMixin
from ._model                    import PeaksPlotModelAccess

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
                                  [u'Events per Cycle', '.1f'],
                                  [u'Down Time Φ₅ (s)', '.1f'],
                                  [u'Sites found',      ''],
                                  [u'Silhouette',       '.1f'],
                                  [u'reduced χ²',       '.1f']]}

    def create(self, _) -> List[Widget]:
        self.__widget = PeaksStatsDiv()
        self.reset(None)
        return [self.__widget]

    def reset(self, resets):
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

            self.values[0] = mdl.stretch
            self.values[1] = mdl.bias
            self.values[2] = rawprecision(mdl.track, mdl.bead)
            if len(mdl.peaks['z']):
                self.values[3] = np.mean(mdl.peaks['sigma'])
            self.values[4] = max(0, len(mdl.peaks['z']) - 1)
            self.values[5] = np.mean(mdl.peaks['count'][1:])/100.
            self.values[6] = np.mean(mdl.peaks['duration'][0])

        def sequencedependant(self, mdl, dist, key):
            "all sequence dependant stats"
            task      = mdl.identification.task
            remove    = task.peakids[key].peaks[[0,-1]]
            nrem      = sum(i in remove for i in mdl.peaks[key+'id'])
            nfound    = np.isfinite(mdl.peaks[key+'id']).sum()-nrem
            npks      = len(task.peakids[key].hybridizations)
            self.values[7] = '{}/{}'.format(nfound, npks)
            if nrem == 2:
                self.values[7] += self.openhp

            self.values[8] = HairpinDistance.silhouette(dist, key)

            if nfound > 2:
                stretch        = dist[key].stretch
                self.values[9] = (np.nanstd(mdl.peaks[key+'id'])
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
        ret = {'': tab()}

        if self._model.identification.task is not None:
            dist = self._model.distances
            for key in self._model.sequences:
                if key in dist:
                    tab.sequencedependant(self._model, dist, key)
                    ret[key] = tab()
        return ret

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
                                   filetypes = '*|xlsx')

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

class AdvancedWidget(AdvancedTaskMixin, WidgetCreator):
    "access to the modal dialog"
    _TITLE = 'Hybridstat Configuration'
    _BODY  = (('Minimum frame count per event', '%(_framecount)d'),
              ('Minimum event count per peak',  '%(_eventcount)d'),
              ('Align on phase 5',              '%(_align5)b'))

    def __init__(self, model:PeaksPlotModelAccess) -> None:
        WidgetCreator.__init__(self, model)
        AdvancedTaskMixin.__init__(self)
        self._outp  = {} # type: Dict[str, Dict[str, Any]]

    _framecount = AdvancedTaskMixin.attr('eventdetection.events.select.minlength')
    _eventcount = AdvancedTaskMixin.attr('peakselection.group.mincount')
    _align5     = AdvancedTaskMixin.none('peakselection.align')
