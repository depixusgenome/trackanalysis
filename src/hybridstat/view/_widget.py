#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
import os
from enum                       import IntEnum, auto
from pathlib                    import Path
from typing                     import Any, Dict, List, Tuple

import numpy                 as np
import bokeh.core.properties as props
from bokeh                      import layouts
from bokeh.models               import (DataTable, TableColumn, CustomJS,
                                        Widget, Div, StringFormatter, Dropdown)


from cleaning.view              import BeadSubtractionModalDescriptor
from eventdetection.view        import AlignmentModalDescriptor
from excelreports.creation      import writecolumns
from peakcalling.tohairpin      import PeakGridFit, ChiSquareFit, Symmetry, Range
from peakfinding.groupby        import FullEm, ByHistogram
from signalfilter               import rawprecision
from tasksequences              import StretchFactor, StretchRange
from tasksequences.view         import (SequenceTicker, SequenceHoverMixin,
                                        OligoListWidget, SequencePathWidget)
from taskcontrol.beadscontrol   import TaskWidgetEnabler
from taskview.modaldialog       import tab
from taskview.toolbar           import FileList
from utils                      import dflt, dataclass
from utils.gui                  import startfile, downloadjs
from utils.logconfig            import getLogger
from view.plots                 import DpxNumberFormatter, CACHE_TYPE
from view.dialog                import FileDialog
from view.pathinput             import PathInput
from view.static                import ROUTE, route
from ._model                    import (PeaksPlotModelAccess, FitToReferenceStore,
                                        PeaksPlotTheme, PeaksPlotDisplay)
from ._model                    import SingleStrandConfig
LOGS = getLogger(__name__)

@dataclass
class ReferenceWidgetTheme:
    "ref widget theme"
    name:   str = "hybridstat.fittoreference.widget"
    title:  str = 'Select a reference track'
    width:  int = 280
    height: int = 32

class ReferenceWidget:
    "Dropdown for choosing the reference"
    __files:  FileList
    __theme:  ReferenceWidgetTheme
    __widget: Dropdown

    def __init__(self, ctrl, model) -> None:
        self.__theme = ctrl.theme.swapmodels(ReferenceWidgetTheme())
        self.__model = model
        self.__files = FileList(ctrl)

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"

        self.__widget = Dropdown(
            name   = 'HS:reference',
            width  = self.__theme.width,
            height = self.__theme.height,
            **self.__data()
        )

        @mainview.actionifactive(ctrl)
        def _py_cb(new):
            inew = int(new.item)
            val  = None if inew < 0 else [i for _, i in self.__files()][inew]
            self.__model.fittoreference.reference = val

        def _observe(old = None, **_):
            if 'reference' in old and mainview.isactive():
                data = self.__data()
                mainview.calllater(lambda: self.__widget.update(**data))

        ctrl.display.observe(FitToReferenceStore().name, _observe)

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

    def _data(self) -> dict:
        out  = super()._data()
        dist = self.__peaks.distances
        if len(dist) == 0 or len(out['menu']) <= 3:
            return out

        menu = [i[0] for i in out['menu'][:-2]]
        menu = (sorted((i for i in menu if i in dist), key = dist.__getitem__)
                + sorted(i for i in menu if i not in dist))

        def _get(i, j):
            if j in dist:
                inds = self._theme.inds
                return inds[i]+' ' if i < len(inds) else ''
            return "" if self.__peaks.identification.task is None else "✗ "

        out['menu'] = ([(_get(i, j)+j, j) for i, j in enumerate(menu)]
                       + out['menu'][-2:])

        ref  = self.__peaks.fittoreference.reference
        if ref is not None and ref != self.__peaks.roottask:
            tmp = self.__peaks.identification.constraints(ref)[0]
            ind = next((i for i, j in enumerate(menu) if j == tmp), None)
            if ind is not None:
                out['menu'][ind] = (self._theme.refcheck+menu[ind], menu[ind])

        for i, j in enumerate(out['menu'][:-2]):
            if out['label'] == j[1]:
                out['label'] = j[0]
        return out

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

class PeaksStatsDiv(Div):  # pylint: disable = too-many-ancestors
    "div for displaying stats"
    data               = props.Dict(props.String, props.String)
    __implementation__ = "peakstats.ts"


_LINE = """
    <div>
        <div class='dpx-span'>
            <div><p style='margin: 0px; width:120px;'><b>{}</b></p></div>
            <div><p style='margin: 0px;'>{}</p></div>
        </div>
    </div>
    """.strip().replace("    ", "").replace("\n", "")

class PeaksStatsOrder(IntEnum):
    "order of information in PeaksStatsWidget"
    cycles       = auto()
    stretch      = auto()
    bias         = auto()
    sigmahf      = auto()
    sigmapeaks   = auto()
    skew         = auto()
    peaks        = auto()
    baseline     = auto()
    singlestrand = auto()
    events       = auto()
    downtime     = auto()
    sites        = auto()
    silhouette   = auto()
    chi2         = auto()

@dataclass  # pylint: disable=too-many-instance-attributes
class PeaksStatsWidgetTheme:
    "PeaksStatsWidgetTheme"
    name:         str = "hybridstat.peaks.stats"
    line:         str = _LINE
    openhairpin:  str = ' & open hairpin'
    orientation:  str = '-+ '
    style:        Dict[str, Any]  = dflt({})
    lines:        List[List[str]] = dflt([
        ['Cycles',            '.0f'],
        ['Stretch (base/µm)', '.3f'],
        ['Bias (µm)',         '.4f'],
        ['σ[HF] (µm)',        '.4f'],
        ['σ[Peaks] (µm)',     '.4f'],
        ['Average Skew ',     '.2f'],
        ['Peak count',        '.0f'],
        ['Baseline (µm)',     '.3f'],
        ['Singlestrand (µm)', '.3f'],
        ['Events per Cycle',  '.1f'],
        ['Down Time Φ₅ (s)',  '.1f'],
        ['Sites found',       ''],
        ['Silhouette',        '.1f'],
        ['reduced χ²',        '.1f']
    ])
    height: int = 20*14
    width:  int = 230

class PeaksStatsWidget:
    "Table containing stats per peaks"
    __widget: PeaksStatsDiv
    __theme:  PeaksStatsWidgetTheme

    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.swapmodels(PeaksStatsWidgetTheme())

    def addtodoc(self, *_) -> List[Widget]:  # pylint: disable=arguments-differ
        "creates the widget"
        self.__widget = PeaksStatsDiv(
            style  = self.__theme.style,
            width  = self.__theme.width,
            height = self.__theme.height,
            css_classes = ['dpx-peakstatdiv']
        )
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
            self.values = ['']*(len(self.titles)+1)
            self.line   = theme.line
            self.openhp = theme.openhairpin

        def trackdependant(self, mdl):
            "all track dependant stats"
            track = mdl.track
            if track is None:
                return

            _   = PeaksStatsOrder
            dim = mdl.instrumentdim
            self.titles = [(i.replace('µm', dim), j) for i,j in self.titles]

            self.values[_.cycles]  = track.ncycles
            self.values[_.sigmahf] = rawprecision(track, mdl.bead)
            if len(mdl.peaks['z']):
                self.values[_.sigmapeaks] = mdl.peaks['sigma']
            self.values[_.skew] = mdl.peaks['skew']
            if len(mdl.peaks['z']):
                self.values[_.peaks]    = len(mdl.peaks['z'])
                self.values[_.events]   = mdl.peaks['count'][1:]/100.
                self.values[_.downtime] = mdl.peaks['duration'][0]
            else:
                self.values[_.peaks]    = 0
                self.values[_.events]   = 0.
                self.values[_.downtime] = np.NaN

            for name in ('baseline', 'singlestrand'):
                val = getattr(mdl.peaksmodel.display, name)
                if val is not None:
                    self.values[getattr(_, name)] = val

        def sequencedependant(self, mdl, dist, key):
            "all sequence dependant stats"
            _                           = PeaksStatsOrder
            task                        = mdl.identification.task
            nfound                      = np.isfinite(mdl.peaks[key+'id']).sum()
            self.values[_.stretch]      = dist[key].stretch
            self.values[_.bias]         = dist[key].bias
            self.values[_.sites]        = f'{nfound}/{len(task.match[key].peaks)}'
            self.values[_.silhouette]   = PeakGridFit.silhouette(dist, key)

            if nfound > 2:
                stretch             = dist[key].stretch
                self.values[_.chi2] = (
                    np.nansum(mdl.peaks[key+'distance']**2)
                    / (
                        (np.mean(self.values[_.sigmahf]*stretch))**2
                        * (nfound - 2)
                    )
                )

        def referencedependant(self, mdl):
            "all sequence dependant stats"
            fittoref       = mdl.fittoreference
            if fittoref.referencepeaks is None:
                return

            self.default(fittoref)

            _                      = PeaksStatsOrder
            nfound                 = np.isfinite(mdl.peaks['id']).sum()
            self.values[_.sites]   = f'{nfound}/{len(fittoref.referencepeaks)}'
            if nfound > 2:
                self.values[_.chi2] = (
                    np.nansum((mdl.peaks['distance'])**2)
                    / (
                        (np.mean(self.values[_.sigmahf]))**2
                        * (nfound - 2)
                    )
                )

        def default(self, mdl):
            "default values"
            _                      = PeaksStatsOrder
            self.values[_.stretch] = mdl.stretch
            self.values[_.bias]    = mdl.bias

        def __call__(self) -> str:
            return ''.join(self.line.format(i[0], self.__fmt(i[1], j))
                           for i, j in zip(self.titles, self.values[1:]))

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
        tbl = self._TableConstructor(self.__theme)
        tbl.trackdependant(self.__model)
        tbl.default(self.__model)
        ret = {'': tbl()}

        if self.__model.identification.task is not None:
            dist = self.__model.distances
            for key in dist:
                tbl.sequencedependant(self.__model, dist, key)
                ret[key] = tbl()

        elif self.__model.fittoreference.task is not None:
            tbl.referencedependant(self.__model)
            ret[''] = tbl()
        return ret

@dataclass
class PeakListTheme:
    "PeakListTheme"
    name:      str             = "hybridstat.peaks.list"
    height:    int             = 400
    colwidth:  int             = 60
    refid:     str             = '0.0000'
    columns:   List[List[str]] = dflt([['z',        'Z (µm)',                 '0.0000'],
                                       ['bases',    'Z (base)',               '0.0'],
                                       ['id',       'Hairpin',                '0'],
                                       ['orient',   'Strand',                 ''],
                                       ['distance', 'Distance',               '0.0'],
                                       ['count',    PeaksPlotTheme.xlabel,    '0.0'],
                                       ['duration', PeaksPlotTheme.xtoplabel, '0.000'],
                                       ['sigma',    'σ (µm)',                 '0.0000'],
                                       ['skew',     'skew',                   '0.00']])

    @property
    def width(self) -> int:
        "the table width"
        return self.colwidth*len(self.columns)

class PeakListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    theme:    PeakListTheme

    def __init__(self, ctrl, model:PeaksPlotModelAccess, theme = None) -> None:
        self.__model = model
        self.theme   = ctrl.theme.swapmodels(PeakListTheme() if theme is None else theme)

    def __cols(self):
        dim = self.__model.instrumentdim

        def _fmt(line):
            return (
                StringFormatter(text_align = 'center') if line == '' else
                DpxNumberFormatter(format = line, text_align = 'right')
            )
        cols  = list(TableColumn(field      = i[0],
                                 title      = i[1].replace("µm", dim),
                                 formatter  = _fmt(i[2]))
                     for i in self.theme.columns)

        isref = (
            self.__model.fittoreference.task is not None
            and self.__model.identification.task is None
        )
        for name in ('id', 'distance'):
            ind = next(i for i, j in enumerate(self.theme.columns) if j[0] == name)
            fmt = self.theme.refid if isref else self.theme.columns[ind][-1]
            cols[ind].formatter.format = fmt
        return cols

    def addtodoc(    # type: ignore # pylint: disable=arguments-differ
            self, _1, _2, src
    ) -> List[Widget]:
        "creates the widget"
        cols  = self.__cols()
        self.__widget = DataTable(
            source         = src,
            columns        = cols,
            editable       = False,
            index_position = None,
            width          = self.theme.width,
            height         = self.theme.height,
            name           = "Peaks:List"
        )
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__widget].update(columns = self.__cols())

class CSVExporter:
    "exports all to csv"

    @staticmethod
    def addtodoc(mainview, *_) -> List['Widget']:
        "creates the widget"
        return [downloadjs(
            mainview.plotfigures[0],
            fname   = "bead.csv",
            tooltip = "Save bead data to CSV",
            src     = mainview.peaksdata,
        )]

    def reset(self, *_):
        "reset all"

@dataclass  # pylint: disable=too-many-instance-attributes
class PeakIDPathTheme:
    "PeakIDPathTheme"
    name:        str       = "hybridstat.peaks.idpath"
    title:       str       = ""
    dialogtitle: str       = 'Select an id file path'
    placeholder: str       = 'Id file path'
    filechecks:  int       = 500
    width:       int       = 225
    height:      int       = 32
    tableerror:  List[str] = dflt(['File extension must be .xlsx', 'warning'])

class PeakIDPathWidget:
    "Selects an id file"
    __widget: PathInput
    __dlg:    FileDialog
    __theme:  PeakIDPathTheme

    def __init__(self, ctrl, model:PeaksPlotModelAccess) -> None:
        self.keeplistening  = True
        self.__peaks        = model
        self.__theme        = ctrl.theme.swapmodels(PeakIDPathTheme())

    def _doresetmodel(self, ctrl):
        mdl  = self.__peaks.identification
        try:
            task = mdl.default(self.__peaks)
        except Exception as exc:  # pylint: disable=broad-except
            LOGS.exception(exc)
            ctrl.display.update(
                "message",
                message = IOError("Failed to read id file", "warning")
            )
            return

        missing = (
            {i[0] for i in task.constraints.values()} - set(task.fit)
            if task else
            set()
        )
        if len(missing):
            msg = f"IDs missing from fasta: {missing}"
            ctrl.display.update("message", message = KeyError(msg, "warning"))
        else:
            with ctrl.action:
                mdl.resetmodel(self.__peaks)

    def callbacks(self, ctrl, doc):
        "sets-up a periodic callback which checks whether the id file has changed"
        finfo = [None, None]

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

            finfo[1] = time  # type: ignore
            if new:
                finfo[0] = path
                return

            if not diff:
                return

            self._doresetmodel(ctrl)

        doc.add_periodic_callback(_callback, self.__theme.filechecks)

    def observe(self, ctrl):
        "sets up observers"
        self.__dlg = FileDialog(
            ctrl,
            storage   = 'constraints.path',
            filetypes = '*|xlsx',
            title     = self.__theme.dialogtitle
        )

    def addtodoc(self, mainview, ctrl,  # type: ignore # pylint: disable=arguments-differ
                 *_) -> List[Widget]:
        "creates the widget"
        self.__widget = PathInput(
            width       = self.__theme.width,
            height      = self.__theme.height,
            placeholder = self.__theme.placeholder,
            title       = self.__theme.title,
            name        = 'Peaks:IDPath'
        )

        @mainview.actionifactive(ctrl)
        def _onclick_cb(attr, old, new):
            path = self.__dlg.open()
            if path is not None:
                self.__widget.value = str(Path(path).resolve())

        @mainview.actionifactive(ctrl)
        def _onchangetext_cb(attr, old, new):
            path = self.__widget.value.strip()
            info = dict(self.__peaks.peaksmodel.display.constraintspath)
            if path == '':
                info.pop(self.__peaks.roottask)
            else:
                info[self.__peaks.roottask] = str(Path(path).resolve())

            if path and not Path(path).exists():
                if not path.endswith(".xlsx"):
                    raise IOError(*self.__theme.tableerror)

                dim = self.__peaks.instrumentdim
                writecolumns(path, "Summary",
                             [('Bead',                  [self.__peaks.bead]),
                              ('Reference',             [self.__peaks.sequencekey]),
                              (f'Stretch (base/{dim})', [self.__peaks.stretch]),
                              (f'Bias ({dim})',         [self.__peaks.bias])])
                startfile(path)

            ctrl.display.update(self.__peaks.peaksmodel.display, constraintspath = info)
            if path:
                self._doresetmodel(ctrl)

        self.__widget.on_change('clicks', _onclick_cb)
        self.__widget.on_change('value',  _onchangetext_cb)
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened, ..."
        txt  = ''
        path = self.__peaks.constraintspath
        if path is not None and Path(path).exists():
            txt = str(Path(path).resolve())
        (self.__widget if resets is None else resets[self.__widget]).update(value = txt)

class DpxFitParams(Widget):
    "Interface to filters needed for cleaning"
    __css__            = route("peaksplot.css")
    __javascript__     = [ROUTE+"/jquery.min.js", ROUTE+"/jquery-ui.min.js"]
    __implementation__ = "_widget.ts"
    frozen             = props.Bool(True)
    stretch            = props.String("")
    bias               = props.String("")
    locksequence       = props.Bool(False)

class FitParamsWidget:
    "All inputs for cleaning"
    RND = dict(stretch = 1, bias   = 4)
    __widget: DpxFitParams

    def __init__(self, _, model:PeaksPlotModelAccess) -> None:
        self.__model = model

    def addtodoc(self, mainview, ctrl, *_) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxFitParams(
            **self.__data(),
            width  = ctrl.theme.get(PeakIDPathTheme(), "width"),
            height = ctrl.theme.get(PeakIDPathTheme(), "height")
        )

        @mainview.actionifactive(ctrl)
        def _on_cb(attr, old, new):
            vals = [self.__widget.locksequence,
                    self.__widget.stretch,
                    self.__widget.bias]
            vals[2 if attr == 'bias' else 1 if attr == 'stretch' else 0] = new
            try:
                status = (self.__model.sequencekey if vals[0] else None,
                          float(vals[1])           if vals[1] else None,
                          float(vals[2])           if vals[2] else None)
            except ValueError:
                self.__widget.update(**{attr: old})
            else:
                fcn    = lambda x, y: np.around(x, self.RND[y]) if x else None  # noqa
                status = status[0], fcn(status[1], "stretch"), fcn(status[2], "bias")
                self.__model.identification.newconstraint(*status)

        for name in ("stretch", "bias", "locksequence"):
            self.__widget.on_change(name, _on_cb)

        return [self.__widget]

    def reset(self, resets:CACHE_TYPE):
        "resets the widget when opening a new file, ..."
        resets[self.__widget].update(self.__data())

    def __data(self):
        "resets the widget when opening a new file, ..."
        ctrl  = self.__model.identification
        cstrs = ctrl.constraints()
        return dict(locksequence = cstrs[0] is not None,
                    stretch      = str(cstrs[1]) if cstrs[1] else "",
                    bias         = str(cstrs[2]) if cstrs[2] else "",
                    frozen       = ctrl.task is None)

class _IdAccessor:
    _LABEL  = '%({self._attrname}){self._fmt}'

    def __init__(self, label):
        self._label    = label[:label.rfind("%(")].strip()
        self._fmt      = label[label.rfind(")")+1:].strip()
        self._attrname = ""

        attr       = label[label.rfind(':')+1:label.rfind(')')]
        self._name = 'match' if attr == 'window' else 'fit'
        if attr == 'alg':
            self._fget = lambda i: isinstance(i, PeakGridFit)
            self._fset = lambda j, i: (
                (ChiSquareFit, PeakGridFit)[i](
                    symmetry = (
                        Symmetry.both if j.symmetry == Symmetry.both else
                        Symmetry.left if i else
                        Symmetry.right
                    ),
                    defaultstretch = j.defaultstretch,
                    stretch        = j.stretch
                ),
            )
        elif attr == 'fpos':
            self._fget = lambda i: i.symmetry == Symmetry.both
            self._fset = lambda j, i: {
                'symmetry': (
                    Symmetry.both if i else
                    Symmetry.left if isinstance(j, PeakGridFit) else
                    Symmetry.right
                )
            }
        elif attr == 'stretch':
            self._fget = lambda i: i.defaultstretch
            self._fset = lambda j, i: {
                'defaultstretch': float(i),
                'stretch':        Range(i, j.stretch[1], j.stretch[2])
            }
        elif attr == 'stretchrange':
            self._fget = lambda i: i.stretch[1]
            self._fset = lambda j, i: {'stretch': Range(j.stretch[0], i, j.stretch[2])}
        elif attr == 'biasrange':
            self._fget = lambda i: i.bias[1]
            self._fset = lambda j, i: {'bias': Range(None, i, j.bias[2])}
        else:
            self._fget = lambda i: getattr(i, attr)
            self._fset = lambda _, i: {attr: i}

    class _Value:
        def __init__(self, tpe):
            self.tpe = tpe

        def __str__(self):
            return  ', '.join(f'{i.name} = {i.value:.1f}' for i in self.tpe.__members__.values())

        def __eq__(self, value):
            return False

    def getdefault(self, inst, usr = False):
        "returns the default value"
        if usr is False:
            if 'Default stretch range' in self._label:
                return self._Value(StretchRange)
            if 'Default stretch' in self._label:
                return self._Value(StretchFactor)
        ident = getattr(inst, '_model').identification
        return self._fget(ident.defaultattribute(self._name, usr))

    def __set_name__(self, _, name):
        self._attrname = name

    def __get__(self, inst, owner):
        return self if inst is None else self.getdefault(inst, True)

    def __set__(self, inst, value):
        if value == self.__get__(inst, inst.__class__):
            return

        mdl   = getattr(inst, '_model')
        ident = getattr(inst, '_model').identification
        val   = self._fset(ident.defaultattribute(self._name, True), value)
        if isinstance(val, dict):
            mdl.identification.updatedefault(self._name, **val)
        else:
            mdl.identification.updatedefault(self._name, *val)
        mdl.identification.resetmodel(mdl)

    def line(self) -> Tuple[str, str]:
        "return the line for this descriptor"
        return self._label, self._LABEL.format(self = self)

class _PeakDescriptor:
    def getdefault(self,inst):
        "returns default peak finder"
        if inst is None:
            return self
        return not isinstance(getattr(inst, '_model').peakselection.defaultconfigtask.finder,
                              ByHistogram)

    def __get__(self,inst,owner) -> bool:
        return not isinstance(getattr(inst,'_model').peakselection.task.finder,ByHistogram)

    def __set__(self,inst,value):
        mdl = getattr(inst,'_model')
        if value:
            mdl.peakselection.update(finder=FullEm(mincount=getattr(inst,"_eventcount")))
            return
        mdl.peakselection.update(finder=ByHistogram(mincount=getattr(inst,"_eventcount")))

def advanced(**kwa):
    "create the advanced button"
    acc  = (
        BeadSubtractionModalDescriptor,
        AlignmentModalDescriptor,
        SingleStrandConfig,
        _IdAccessor
    )
    acc += tuple(kwa.get('accessors', ()))  # type: ignore
    return tab(
        f"""
        ## Cleaning

        Discard z(∈ φ₅) < z(φ₁)-σ[HF]⋅α                    %(clipping.lowfactor).1oF
        %(BeadSubtractionModalDescriptor:)
        %(AlignmentModalDescriptor:)
        Discard the single strand peak (unless in oligos)  %(SingleStrandConfig:automated)b
        Detect and discard peaks below the baseline        %(baselinefilter.disabled)b

        ## Peaks

        ### Events in Peaks
        Phase with events                       %(eventdetection.phase)D
        Min frame count per hybridisation       %(eventdetection.events.select.minlength)D
        Min hybridisations per peak             %(peakselection.finder.grouper.mincount)D
        Re-align cycles using peaks             %(peakselection.align)b
        {kwa.pop('peakstext', '')}

        ### Fitting Algorithm
        * \u261B To fit to the baseline (singlestrand) peak, *
        * \u261B add '0' ('$' or 'singlestrand') to oligos. *

        Peak kernel size (blank ⇒ auto)         %(peakselection.precision).4oF
        Expected stretch (bases per µm)         %(_IdAccessor:stretch).0F
        Stretch range (bases per µm)            %(_IdAccessor:stretchrange)D
        Bias range (µm)                         %(_IdAccessor:biasrange).3F
        Exhaustive fit algorithm                %(_IdAccessor:alg)b
        Score is affected by false positives    %(_IdAccessor:fpos)b

        ### Binding Position Identification
        Max Δ to theoretical peak               %(_IdAccessor:window)d
        """,
        accessors = {i.__name__: i for i in acc},
        figure    = kwa if kwa else (PeaksPlotTheme, PeaksPlotDisplay),
        base      = tab.taskwidget
    )

class PeaksPlotWidgets:  # pylint: disable=too-many-instance-attributes
    "peaks plot widgets"
    enabler: TaskWidgetEnabler

    def __init__(self, ctrl, mdl: PeaksPlotModelAccess, **kwa) -> None:
        "returns a dictionnary of widgets"
        self.seq       = PeaksSequencePathWidget(ctrl, mdl)
        self.ref       = ReferenceWidget(ctrl, mdl)
        self.oligos    = OligoListWidget(ctrl, )
        self.stats     = PeaksStatsWidget(ctrl, mdl)
        self.peaks     = PeakListWidget(ctrl, mdl, kwa.pop('peaks', None))
        self.cstrpath  = PeakIDPathWidget(ctrl, mdl)
        self.fitparams = FitParamsWidget(ctrl, mdl)
        self.advanced  = advanced(**kwa)(ctrl, mdl)
        self.csv       = CSVExporter()

    def addtodoc(self, mainview, ctrl, doc):
        "creates the widget"
        wdg = self._create(mainview, ctrl, doc)
        return self._assemble(mainview.defaultsizingmode(), wdg)

    def observe(self, ctrl):
        "oberver"
        for widget in self.__dict__.values():
            if hasattr(widget, 'observe'):
                widget.observe(ctrl)

    def reset(self, cache, disable):
        "oberver"
        for key, widget in self.__dict__.items():
            if key != 'enabler':
                widget.reset(cache)
        self.enabler.disable(cache, disable)

    @staticmethod
    def resize(sizer, borders:int, height:int):
        "resize elements in the sizer"
        wbox    = lambda x: x.update(    # noqa
            width  = max(i.width  for i in x.children),
            height = sum(i.height for i in x.children)
        )

        stats = sizer.children[0].children[1].children[0]
        pks   = sizer.children[1].children[0]
        for i in sizer.children[0].children[0].children:
            i.width = pks.width - stats.width - borders
        wbox(sizer.children[0].children[0])
        sizer.children[0].children[0].width += borders
        wbox(sizer.children[0].children[1])
        sizer.children[0].update(
            width  = sum(i.width  for i in sizer.children[0].children),
            height = max(i.height for i in sizer.children[0].children),
        )

        pks.height = height - max(sizer.children[0].height, stats.height)
        wbox(sizer.children[1])
        wbox(sizer)
        sizer.width += borders

    def _create(self, mainview, ctrl, doc):
        wdg    = {
            i: j.addtodoc(mainview, ctrl, mainview.peaksdata)
            for i, j in self.__dict__.items()
        }

        enable = dict(wdg)
        enable.pop('fitparams')
        self.enabler = TaskWidgetEnabler(enable)
        self.enabler.extend(mainview.plotfigures)

        self.cstrpath.callbacks(ctrl, doc)
        if hasattr(mainview, 'hover'):
            self.seq.callbacks(
                mainview.hover, mainview.ticker, wdg['stats'][-1], wdg['peaks'][-1]
            )
        self.advanced.callbacks(doc)
        return wdg

    @staticmethod
    def _assemble(mode, wdg):
        wbox  = lambda x: layouts.widgetbox(children = x, **mode)  # noqa
        order = 'ref', 'seq', 'fitparams', 'oligos', 'cstrpath', 'advanced', "csv"
        return layouts.column(
            [
                layouts.row(
                    [
                        wbox(sum((wdg[i] for i in order), [])),
                        wbox(wdg['stats'])
                    ],
                    **mode
                ),
                wbox(wdg['peaks'])
            ],
            **mode
        )
