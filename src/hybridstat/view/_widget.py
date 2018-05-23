#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
import os
from pathlib               import Path
from typing                import Any, Dict, List

import numpy                 as np
import bokeh.core.properties as props
from bokeh.models               import (DataTable, TableColumn, CustomJS,
                                        Widget, Div, StringFormatter, Paragraph,
                                        Dropdown)

from signalfilter               import rawprecision

from peakcalling.tohairpin      import PeakGridFit, ChiSquareFit
from peakfinding.groupby        import ByEM, ByHistogram
from utils                      import initdefaults
from utils.gui                  import startfile
from excelreports.creation      import writecolumns
from eventdetection.view        import AlignmentModalDescriptor
from cleaning.view              import BeadSubtractionModalDescriptor
from view.dialog                import FileDialog
from view.pathinput             import PathInput
from view.plots                 import DpxNumberFormatter
from view.toolbar               import FileList
from sequences.view             import (SequenceTicker, SequenceHoverMixin,
                                        OligoListWidget, SequencePathWidget)
from modaldialog.view           import AdvancedTaskMixin, T_BODY
from ._model                    import PeaksPlotModelAccess, FitToReferenceStore

class ReferenceWidgetTheme:
    "ref widget theme"
    name  = "hybridstat.fittoreference.widget"
    title = 'Reference Track'
    none  = 'None'
    width = 280
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class ReferenceWidget:
    "Dropdown for choosing the reference"
    __files : FileList
    __theme : ReferenceWidgetTheme
    __widget: Dropdown
    def __init__(self, ctrl, model) -> None:
        self.__theme = ctrl.theme.add(ReferenceWidgetTheme())
        self.__model = model
        self.__files = FileList(ctrl)

    def observe(self, ctrl):
        "sets up observers"
        def _observe(old = None, **_):
            if 'reference' in old:
                self.__widget.update(**self.__data())
        ctrl.display.observe(FitToReferenceStore.name, _observe)

    def addtodoc(self, ctrl, *_) -> List[Widget]:
        "creates the widget"
        self.__widget = Dropdown(name  = 'HS:reference',
                                 width = self.__theme.width,
                                 **self.__data())
        @ctrl.action
        def _py_cb(new):
            inew = int(new)
            val  = None if inew < 0 else [i for _, i in self.__files()][inew]
            self.__model.fittoreference.reference = val

        self.__widget.on_click(_py_cb)
        return [Paragraph(text = self.__theme.title), self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

    @property
    def widget(self):
        "returns the widget"
        return self.__widget

    def __data(self) -> dict:
        lst   = list(self.__files())
        menu  = [(j, str(i)) for i, j in enumerate(i for i, _ in lst)]
        menu += [None, (self.__theme.none, '-1')]

        key   = self.__model.fittoreference.reference
        index = -1 if key is None else [i for _, i in lst].index(key)
        return dict(menu  = menu, label = menu[index][0], value = str(index))

class PeaksSequencePathWidget(SequencePathWidget):
    "Widget for setting the sequence to use"
    def __init__(self, ctrl, mdl: PeaksPlotModelAccess) -> None:
        super().__init__(ctrl)
        self.__peaks = mdl

    def _sort(self, lst) -> List[str]: # type: ignore
        dist = self.__peaks.distances
        if len(dist):
            lst  = [i for i in lst if i in dist]
            return sorted(lst, key = lambda i: dist[i].value)
        return super()._sort(lst)

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

_LINE = """
    <div>
        <div class='dpx-span'>
            <div><p style='margin: 0px; width:120px;'><b>{}</b></p></div>
            <div><p style='margin: 0px;'>{}</p></div>
        </div>
    </div>
    """.strip().replace("    ", "").replace("\n", "")

class PeaksStatsWidgetTheme:
    "PeaksStatsWidgetTheme"
    name        = "hybridstat.peaks.stats"
    line        = _LINE
    openhairpin =  ' & open hairpin'
    orientation = u'-+ '
    style       = {'padding-top': '40px'}
    lines       = [['cycles',            '.0f'],
                   ['Stretch (base/µm)', '.3f'],
                   ['Bias (µm)',         '.4f'],
                   ['σ[HF] (µm)',        '.4f'],
                   ['σ[Peaks] (µm)',     '.4f'],
                   ['Average Skew ',     '.2f'],
                   ['Peak count',        '.0f'],
                   ['Events per Cycle',  '.1f'],
                   ['Down Time Φ₅ (s)',  '.1f'],
                   ['Sites found',       ''],
                   ['Silhouette',        '.1f'],
                   ['reduced χ²',        '.1f']]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class PeaksStatsWidget:
    "Table containing stats per peaks"
    __widget: PeaksStatsDiv
    __theme : PeaksStatsWidgetTheme
    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(PeaksStatsWidgetTheme())

    def addtodoc(self, *_) -> List[Widget]: # pylint: disable=arguments-differ
        "creates the widget"
        self.__widget = PeaksStatsDiv(style = self.__theme.style)
        self.reset(None)
        return [self.__widget]

    def reset(self, resets):
        "resets the widget upon opening a new file, ..."
        itm  = self.__widget if resets is None else resets[self.__widget]
        data = self.__data()
        itm.update(data = data, text = data.get(self.__model.sequencekey, data['']))

    class _TableConstructor:
        "creates the html table containing stats"
        def __init__(self, theme: PeaksStatsWidgetTheme) -> None:
            self.titles = [tuple(i) for i in theme.lines]
            self.values = ['']*len(self.titles)
            self.line   = theme.line
            self.openhp = theme.openhairpin

        def trackdependant(self, mdl):
            "all track dependant stats"
            if mdl.track is None:
                return

            self.values[0] = mdl.track.ncycles
            self.values[3] = rawprecision(mdl.track, mdl.bead)
            if len(mdl.peaks['z']):
                self.values[4] = mdl.peaks['sigma']
            self.values[5] = mdl.peaks['skew']
            self.values[6] = max(0, len(mdl.peaks['z']) - 1)
            self.values[7] = 0.     if self.values[6] < 1 else mdl.peaks['count'][1:]/100.
            self.values[8] = np.NaN if self.values[6] < 1 else mdl.peaks['duration'][0]

        def sequencedependant(self, mdl, dist, key):
            "all sequence dependant stats"
            self.values[1] = dist[key].stretch
            self.values[2] = dist[key].bias

            task      = mdl.identification.task
            tmp       = task.match[key].peaks
            if len(tmp):
                remove = task.match[key].peaks[[0,-1]]
                nrem   = sum(i in remove for i in mdl.peaks[key+'id'])
            else:
                nrem   = 0
            nfound         = np.isfinite(mdl.peaks[key+'id']).sum()-nrem
            self.values[9] = f'{nfound}/{len(task.match[key].hybridisations)}'
            if nrem == 2:
                self.values[9] += self.openhp

            self.values[10] = PeakGridFit.silhouette(dist, key)

            if nfound > 2:
                stretch         = dist[key].stretch
                self.values[10] = (np.nansum(mdl.peaks[key+'distance']**2)
                                   / ((np.mean(self.values[3]*stretch))**2
                                      * (nfound - 2)))

        def referencedependant(self, mdl):
            "all sequence dependant stats"
            fittoref       = mdl.fittoreference
            if fittoref.referencepeaks is None:
                return

            self.values[0] = fittoref.stretch
            self.values[1] = fittoref.bias

            nfound          = np.isfinite(mdl.peaks['id']).sum()
            self.values[8]  = f'{nfound}/{len(fittoref.referencepeaks)}'
            if nfound > 2:
                self.values[10] = (np.nansum((mdl.peaks['distance'])**2)
                                   / ((np.mean(self.values[3]))**2
                                      * (nfound - 2)))

        def __call__(self) -> str:
            return ''.join(self.line.format(i[0], self.__fmt(i[1], j))
                           for i, j in zip(self.titles, self.values))

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
        tab = self._TableConstructor(self.__theme)
        tab.trackdependant(self.__model)
        ret = {'': tab()}

        if self.__model.identification.task is not None:
            dist = self.__model.distances
            for key in dist:
                tab.sequencedependant(self.__model, dist, key)
                ret[key] = tab()

        elif self.__model.fittoreference.task is not None:
            tab.referencedependant(self.__model)
            ret[''] = tab()
        return ret

class PeakListTheme:
    "PeakListTheme"
    name       = "hybridstat.peaks.list"
    height     = 400
    colwidth   = 60
    refid      = '0.0000'
    columns    = [['z',        'Z (µm)',        '0.0000'],
                  ['bases',    u'Z (base)',     '0.0'],
                  ['id',       u'Id',           '0'],
                  ['orient',   u'Strand',       ''],
                  ['distance', u'Distance',     '0.0'],
                  ['count',    'css:xlabel',    '0.0'],
                  ['duration', 'css:xtoplabel', '0.000'],
                  ['sigma',    u'σ (µm)',       '0.0000'],
                  ['skew',     u'skew',         '0.00']]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class PeakListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    __theme:  PeakListTheme
    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(PeakListTheme())

    def __cols(self):
        fmt   = lambda i: (StringFormatter(text_align = 'center',
                                           font_style = 'bold') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = i[1],
                                 formatter  = fmt(i[2]))
                     for i in self.__theme.columns)

        isref = (self.__model.fittoreference.task is not None and
                 self.__model.identification.task is None)
        for name in ('id', 'distance'):
            ind = next(i for i, j in enumerate(self.__theme.columns) if j[0] == name)
            fmt = self.__theme.refid if isref else self.__theme.columns[ind][-1]
            cols[ind].formatter.format = fmt
        return cols

    def addtodoc(self, _, src) -> List[Widget]: # type: ignore # pylint: disable=arguments-differ
        "creates the widget"
        cols  = self.__cols()
        self.__widget = DataTable(source         = src,
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = self.__theme.colwidth*len(cols),
                                  height         = self.__theme.height,
                                  name           = "Peaks:List")
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__widget].update(columns = self.__cols())

class PeakIDPathTheme:
    "PeakIDPathTheme"
    name       = "hybridstat.peaks.idpath"
    title      = 'Id file path'
    filechecks = 500
    width      = 225
    tableerror = ('File extension must be .xlsx', 'warning')
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class PeakIDPathWidget:
    "Selects an id file"
    __widget: PathInput
    __dlg   : FileDialog
    __theme : PeakIDPathTheme
    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self.keeplistening  = True
        self.__peaks        = model
        self.__theme        = ctrl.theme.add(PeakIDPathTheme())

    def listentofile(self, doc, action):
        "sets-up a periodic callback which checks whether the id file has changed"
        finfo = [None, None]

        @action
        def _do_resetmodel():
            self.__peaks.identification.resetmodel(self.__peaks)

        def _callback():
            if not self.keeplistening:
                return

            path = self.__peaks.constraintspath
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

        doc.add_periodic_callback(_callback, self.__theme.filechecks)

    def observe(self, ctrl):
        "sets up observers"
        self.__dlg = FileDialog(ctrl,
                                storage   = 'constraints.path',
                                filetypes = '*|xlsx')

    def addtodoc(self, ctrl, # type: ignore # pylint: disable=arguments-differ
                 _) -> List[Widget]:
        "creates the widget"
        self.__widget = PathInput(width = self.__theme.width, title = self.__theme.title,
                                  placeholder = "", value = "",
                                  name = 'Peaks:IDPath')

        @ctrl.action
        def _onclick_cb(attr, old, new):
            path = self.__dlg.open()
            if path is not None:
                self.__widget.value = str(Path(path).resolve())

        @ctrl.action
        def _onchangetext_cb(attr, old, new):
            path = self.__widget.value.strip()
            if path == '':
                ctrl.display.update(self.__peaks.peaksmodel.display, constraintspath = None)
                return

            elif not Path(path).exists():
                if not path.endswith(".xlsx"):
                    raise IOError(*self.__theme.tableerror)
                try:
                    writecolumns(path, "Summary",
                                 [('Bead', [self.__peaks.bead]),
                                  ('Reference', [self.__peaks.sequencekey]),
                                  ('Stretch (base/µm)', [self.__peaks.stretch]),
                                  ('Bias (µm)', [self.__peaks.bias])])
                except:
                    raise
                else:
                    startfile(path)

            ctrl.display.update(self.__peaks.peaksmodel.display,
                                constraintspath = str(Path(path).resolve()))

        self.__widget.on_change('click', _onclick_cb)
        self.__widget.on_change('value', _onchangetext_cb)

        self.__dlg.title = self.__theme.title
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened, ..."
        txt  = ''
        path = self.__peaks.constraintspath
        if path is not None and Path(path).exists():
            txt = str(Path(path).resolve())
        (self.__widget if resets is None else resets[self.__widget]).update(value = txt)

class _IdAccessor:
    def __init__(self, name, getter, setter):
        self._name = name
        self._fget = getter
        self._fset = setter

    def getdefault(self, inst):
        "returns the default value"
        return self._fget(getattr(inst, '_model').identification.default(self._name, False))

    def __get__(self, inst, owner):
        if inst is None:
            return self

        return self._fget(getattr(inst, '_model').identification.default(self._name))

    def __set__(self, inst, value):
        if value == self.__get__(inst, inst.__class__):
            return

        mdl = getattr(inst, '_model')
        val = self._fset(value)
        if isinstance(val, dict):
            mdl.identification.updatedefault(self._name, **val)
        else:
            mdl.identification.updatedefault(self._name, *val)
        mdl.identification.resetmodel(mdl)

class _PeakDescriptor:
    def getdefault(self,inst):
        "returns default peak finder"
        if inst is None:
            return self
        return not isinstance(getattr(inst, '_model').peakselection.defaultconfigtask.finder,
                              ByHistogram)

    def __get__(self,inst,owner)->bool:
        return not isinstance(getattr(inst,'_model').peakselection.task.finder,ByHistogram)

    def __set__(self,inst,value):
        mdl = getattr(inst,'_model')
        if value:
            mdl.peakselection.update(finder=ByEM(mincount=getattr(inst,"_eventcount")))
            return
        mdl.peakselection.update(finder=ByHistogram(mincount=getattr(inst,"_eventcount")))

class AdvancedWidget(AdvancedTaskMixin):
    "access to the modal dialog"
    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self._model = model
        super().__init__(ctrl)
        self._outp: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _title() -> str:
        return 'Hybridstat Configuration'

    def _body(self) -> T_BODY:
        cls = type(self)
        return (getattr(cls, '_subtracted').line(),
                getattr(cls, '_alignment').line(),
                ('Minimum frame count per event',    ' %(_framecount)d'),
                ('Minimum event count per peak',     ' %(_eventcount)d'),
                ('Align cycles using peaks',         ' %(_align5)b'),
                ('Peak kernel size (blank ⇒ auto)',  ' %(_precision)of'),
                #('Use EM to find peaks',     '         %(_useem)b'),
                ('Exhaustive fit algorithm',         ' %(_fittype)b'),
                ('Use a theoretical peak 0 in fits', ' %(_peak0)b'),
                ('Max distance to theoretical peak', ' %(_dist2theo)d'),
               )

    def reset(self, resets):
        "resets the widget when a new file is opened, ..."
        AdvancedTaskMixin.reset(resets)

    _subtracted = BeadSubtractionModalDescriptor()
    _alignment  = AlignmentModalDescriptor()
    _framecount = AdvancedTaskMixin.attr('eventdetection.events.select.minlength')
    _eventcount = AdvancedTaskMixin.attr('peakselection.finder.grouper.mincount')
    _align5     = AdvancedTaskMixin.none('peakselection.align')
    _precision  = AdvancedTaskMixin.attr('peakselection.precision')
    _useem      = _PeakDescriptor()
    _peak0      = _IdAccessor('fit', lambda i: i.firstpeak, lambda i: {'firstpeak': i})
    _fittype    = _IdAccessor('fit',
                              lambda i: isinstance(i, PeakGridFit),
                              lambda i: ((ChiSquareFit, PeakGridFit)[i](),))
    _dist2theo  = _IdAccessor('match', lambda i: i.window, lambda i: {'window': i})

def createwidgets(ctrl, mdl: PeaksPlotModelAccess) -> Dict[str, Any]:
    "returns a dictionnary of widgets"
    return dict(seq      = PeaksSequencePathWidget(ctrl, mdl),
                ref      = ReferenceWidget(ctrl, mdl),
                oligos   = OligoListWidget(ctrl, ),
                stats    = PeaksStatsWidget(ctrl, mdl),
                peaks    = PeakListWidget(ctrl, mdl),
                cstrpath = PeakIDPathWidget(ctrl, mdl),
                advanced = AdvancedWidget(ctrl, mdl))
