#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
import os
from pathlib               import Path
from typing                import Any, Dict, List, Optional

import numpy                 as np
import bokeh.core.properties as props
from bokeh.models               import (DataTable, TableColumn, CustomJS,
                                        Widget, Div, StringFormatter, Dropdown)


from cleaning.view              import BeadSubtractionModalDescriptor
from cyclesplot                 import ThemeNameDescriptor, FigureSizeDescriptor
from eventdetection.view        import AlignmentModalDescriptor
from excelreports.creation      import writecolumns
from modaldialog.view           import AdvancedTaskMixin, T_BODY
from peakcalling.tohairpin      import PeakGridFit, ChiSquareFit
from peakfinding.groupby        import FullEm, ByHistogram
from sequences.view             import (SequenceTicker, SequenceHoverMixin,
                                        OligoListWidget, SequencePathWidget)
from signalfilter               import rawprecision
from utils                      import dflt, dataclass
from utils.gui                  import startfile
from view.dialog                import FileDialog
from view.pathinput             import PathInput
from view.plots                 import DpxNumberFormatter
from view.toolbar               import FileList
from ._model                    import (PeaksPlotModelAccess, FitToReferenceStore,
                                        PeaksPlotTheme)

@dataclass
class ReferenceWidgetTheme:
    "ref widget theme"
    name  : str = "hybridstat.fittoreference.widget"
    title : str = 'Select a reference track'
    width : int = 280

class ReferenceWidget:
    "Dropdown for choosing the reference"
    __files : FileList
    __theme : ReferenceWidgetTheme
    __widget: Dropdown
    def __init__(self, ctrl, model) -> None:
        self.__theme = ctrl.theme.add(ReferenceWidgetTheme())
        self.__model = model
        self.__files = FileList(ctrl)

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"

        self.__widget = Dropdown(name  = 'HS:reference',
                                 width = self.__theme.width,
                                 **self.__data())

        @mainview.actionifactive(ctrl)
        def _py_cb(new):
            inew = int(new)
            val  = None if inew < 0 else [i for _, i in self.__files()][inew]
            self.__model.fittoreference.reference = val

        def _observe(old = None, **_):
            if 'reference' in old and mainview.isactive():
                data = self.__data()
                mainview.calllater(lambda: self.__widget.update(**data))

        ctrl.display.observe(FitToReferenceStore.name, _observe)

        self.__widget.on_click(_py_cb)
        return [self.__widget]

    def reset(self, resets):
        "updates the widget"
        resets[self.__widget].update(**self.__data())

    @property
    def widget(self):
        "returns the widget"
        return self.__widget

    def __data(self) -> dict:
        lst        = list(self.__files())
        menu: list = [(j, str(i)) for i, j in enumerate(i for i, _ in lst)]
        menu      += [None, (self.__theme.title, '-1')]

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

    # pylint: disable=arguments-differ
    def callbacks(self,  # type: ignore
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

@dataclass
class PeaksStatsWidgetTheme:
    "PeaksStatsWidgetTheme"
    name        : str = "hybridstat.peaks.stats"
    line        : str = _LINE
    openhairpin : str =  ' & open hairpin'
    orientation : str = '-+ '
    style       : Dict[str, Any]  = dflt({})
    lines       : List[List[str]] = dflt([['cycles',            '.0f'],
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
                                          ['reduced χ²',        '.1f']])

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

@dataclass
class PeakListTheme:
    "PeakListTheme"
    name     : str             = "hybridstat.peaks.list"
    height   : int             = 400
    colwidth : int             = 60
    refid    : str             = '0.0000'
    columns  : List[List[str]] = dflt([['z',        'Z (µm)',                 '0.0000'],
                                       ['bases',    'Z (base)',               '0.0'],
                                       ['id',       'Id',                     '0'],
                                       ['orient',   'Strand',                 ''],
                                       ['distance', 'Distance',               '0.0'],
                                       ['count',    PeaksPlotTheme.xlabel,    '0.0'],
                                       ['duration', PeaksPlotTheme.xtoplabel, '0.000'],
                                       ['sigma',    'σ (µm)',                 '0.0000'],
                                       ['skew',     'skew',                   '0.00']])

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

    def addtodoc(self, _1, _2, src) -> List[Widget]: # type: ignore # pylint: disable=arguments-differ
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

@dataclass
class PeakIDPathTheme:
    "PeakIDPathTheme"
    name       : str           = "hybridstat.peaks.idpath"
    title      : Optional[str] = None
    placeholder: str           = 'Id file path'
    filechecks : int           = 500
    width      : int           = 225
    tableerror : List[str]     = dflt(['File extension must be .xlsx', 'warning'])

class PeakIDPathWidget:
    "Selects an id file"
    __widget: PathInput
    __dlg   : FileDialog
    __theme : PeakIDPathTheme
    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self.keeplistening  = True
        self.__peaks        = model
        self.__theme        = ctrl.theme.add(PeakIDPathTheme())

    def callbacks(self, ctrl, doc):
        "sets-up a periodic callback which checks whether the id file has changed"
        finfo = [None, None]

        @ctrl.action
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
        self.__dlg = FileDialog(ctrl, storage = 'constraints.path', filetypes = '*|xlsx')

    def addtodoc(self, mainview, ctrl, # type: ignore # pylint: disable=arguments-differ
                 _) -> List[Widget]:
        "creates the widget"
        self.__widget = PathInput(width       = self.__theme.width,
                                  placeholder = self.__theme.placeholder,
                                  title       = self.__theme.title,
                                  name        = 'Peaks:IDPath')

        @mainview.actionifactive(ctrl)
        def _onclick_cb(attr, old, new):
            path = self.__dlg.open()
            if path is not None:
                self.__widget.value = str(Path(path).resolve())

        @mainview.actionifactive(ctrl)
        def _onchangetext_cb(attr, old, new):
            path = self.__widget.value.strip()
            if path == '':
                ctrl.display.update(self.__peaks.peaksmodel.display, constraintspath = None)
                return

            if not Path(path).exists():
                if not path.endswith(".xlsx"):
                    raise IOError(*self.__theme.tableerror)

                writecolumns(path, "Summary",
                             [('Bead', [self.__peaks.bead]),
                              ('Reference', [self.__peaks.sequencekey]),
                              ('Stretch (base/µm)', [self.__peaks.stretch]),
                              ('Bias (µm)', [self.__peaks.bias])])
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

class _SingleStrandDescriptor:
    def getdefault(self,inst):
        "returns default single strand suppression"
        return (self if inst is None else
                not getattr(inst,'_model').singlestrand.configtask.disabled)

    def __get__(self,inst,owner) -> bool:
        return getattr(inst,'_model').singlestrand.task is not None

    def __set__(self,inst, value):
        getattr(inst,'_model').singlestrand.update(disabled = not value)

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
            mdl.peakselection.update(finder=FullEm(mincount=getattr(inst,"_eventcount")))
            return
        mdl.peakselection.update(finder=ByHistogram(mincount=getattr(inst,"_eventcount")))

class AdvancedWidget(AdvancedTaskMixin):
    "access to the modal dialog"
    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self._model = model
        super().__init__(ctrl)
        self._outp: Dict[str, Dict[str, Any]] = {}
        self._ctrl = ctrl

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
                ('Discard the single strand peak',   ' %(_singlestrand)b'),
                ('Use a theoretical peak 0 in fits', ' %(_peak0)b'),
                ('Exhaustive fit algorithm',         ' %(_fittype)b'),
                ('Max distance to theoretical peak', ' %(_dist2theo)d'),
                *(getattr(cls, i).line for i in ('_themename', '_figwidth', '_figheight'))
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
    #_useem      = _PeakDescriptor()
    _singlestrand = _SingleStrandDescriptor()
    _peak0      = _IdAccessor('fit', lambda i: i.firstpeak, lambda i: {'firstpeak': i})
    _fittype    = _IdAccessor('fit',
                              lambda i: isinstance(i, PeakGridFit),
                              lambda i: ((ChiSquareFit, PeakGridFit)[i](),))
    _dist2theo  = _IdAccessor('match', lambda i: i.window, lambda i: {'window': i})
    _themename  = ThemeNameDescriptor()
    _figwidth   = FigureSizeDescriptor(PeaksPlotTheme.name)
    _figheight  = FigureSizeDescriptor(PeaksPlotTheme.name)

def createwidgets(ctrl, mdl: PeaksPlotModelAccess) -> Dict[str, Any]:
    "returns a dictionnary of widgets"
    return dict(seq      = PeaksSequencePathWidget(ctrl, mdl),
                ref      = ReferenceWidget(ctrl, mdl),
                oligos   = OligoListWidget(ctrl, ),
                stats    = PeaksStatsWidget(ctrl, mdl),
                peaks    = PeakListWidget(ctrl, mdl),
                cstrpath = PeakIDPathWidget(ctrl, mdl),
                advanced = AdvancedWidget(ctrl, mdl))
