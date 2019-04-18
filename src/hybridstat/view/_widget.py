#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Shows peaks as found by peakfinding vs theory as fit by peakcalling"
import os
from pathlib               import Path
from typing                import Any, Dict, List, Optional, Tuple

import numpy                 as np
import bokeh.core.properties as props
from bokeh.models               import (DataTable, TableColumn, CustomJS,
                                        Widget, Div, StringFormatter, Dropdown)


from cleaning.view              import BeadSubtractionModalDescriptor
from eventdetection.view        import AlignmentModalDescriptor
from excelreports.creation      import writecolumns
from peakcalling.tohairpin      import PeakGridFit, ChiSquareFit
from peakfinding.groupby        import FullEm, ByHistogram
from signalfilter               import rawprecision
from tasksequences.view         import (SequenceTicker, SequenceHoverMixin,
                                        OligoListWidget, SequencePathWidget)
from taskcontrol.beadscontrol   import TaskWidgetEnabler
from taskview.modaldialog       import tab
from taskview.toolbar           import FileList
from utils                      import dflt, dataclass
from utils.gui                  import startfile
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
    name  : str = "hybridstat.fittoreference.widget"
    title : str = 'Select a reference track'
    width : int = 280

class ReferenceWidget:
    "Dropdown for choosing the reference"
    __files : FileList
    __theme : ReferenceWidgetTheme
    __widget: Dropdown
    def __init__(self, ctrl, model) -> None:
        self.__theme = ctrl.theme.add(ReferenceWidgetTheme(), noerase = False)
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
                +sorted(i for i in menu if i not in dist))

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
        self.__theme = ctrl.theme.add(PeaksStatsWidgetTheme(), noerase = False)

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
            dim         = mdl.track.instrument['dimension']
            self.titles = [(i.replace('µm', dim), j) for i,j in self.titles]

            self.values[0] = mdl.track.ncycles
            self.values[3] = rawprecision(mdl.track, mdl.bead)
            if len(mdl.peaks['z']):
                self.values[4] = mdl.peaks['sigma']
            self.values[5] = mdl.peaks['skew']
            self.values[6] = len(mdl.peaks['z'])
            self.values[7] = 0.     if self.values[6] < 1 else mdl.peaks['count'][1:]/100.
            self.values[8] = np.NaN if self.values[6] < 1 else mdl.peaks['duration'][0]

        def sequencedependant(self, mdl, dist, key):
            "all sequence dependant stats"
            self.values[1] = dist[key].stretch
            self.values[2] = dist[key].bias

            task             = mdl.identification.task
            nfound           = np.isfinite(mdl.peaks[key+'id']).sum()
            self.values[9]   = f'{nfound}/{len(task.match[key].peaks)}'
            self.values[10]  = PeakGridFit.silhouette(dist, key)

            if nfound > 2:
                stretch         = dist[key].stretch
                self.values[11] = (np.nansum(mdl.peaks[key+'distance']**2)
                                   / ((np.mean(self.values[3]*stretch))**2
                                      * (nfound - 2)))

        def referencedependant(self, mdl):
            "all sequence dependant stats"
            fittoref       = mdl.fittoreference
            if fittoref.referencepeaks is None:
                return

            self.values[1] = fittoref.stretch
            self.values[2] = fittoref.bias

            nfound          = np.isfinite(mdl.peaks['id']).sum()
            self.values[9]  = f'{nfound}/{len(fittoref.referencepeaks)}'
            if nfound > 2:
                self.values[10] = (np.nansum((mdl.peaks['distance'])**2)
                                   / ((np.mean(self.values[3]))**2
                                      * (nfound - 2)))
        def default(self, mdl):
            "default values"
            self.values[1] = mdl.stretch
            self.values[2] = mdl.bias

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
    name     : str             = "hybridstat.peaks.list"
    height   : int             = 400
    colwidth : int             = 60
    refid    : str             = '0.0000'
    columns  : List[List[str]] = dflt([['z',        'Z (µm)',                 '0.0000'],
                                       ['bases',    'Z (base)',               '0.0'],
                                       ['id',       'Hairpin',                '0'],
                                       ['orient',   'Strand',                 ''],
                                       ['distance', 'Distance',               '0.0'],
                                       ['count',    PeaksPlotTheme.xlabel,    '0.0'],
                                       ['duration', PeaksPlotTheme.xtoplabel, '0.000'],
                                       ['sigma',    'σ (µm)',                 '0.0000'],
                                       ['skew',     'skew',                   '0.00']])

class PeakListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    theme:  PeakListTheme
    def __init__(self, ctrl, model:PeaksPlotModelAccess, theme = None) -> None:
        self.__ctrl  = ctrl
        self.__model = model
        self.theme   = ctrl.theme.add(PeakListTheme() if theme is None else theme,
                                      noerase = False)

    def __cols(self, ctrl):
        track = ctrl.tasks.track(ctrl.display.get("tasks", "roottask"))
        dim   = track.instrument['dimension'] if track else 'µm'
        fmt   = lambda i: (StringFormatter(text_align = 'center') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = i[1].replace("µm", dim),
                                 formatter  = fmt(i[2]))
                     for i in self.theme.columns)

        isref = (self.__model.fittoreference.task is not None and
                 self.__model.identification.task is None)
        for name in ('id', 'distance'):
            ind = next(i for i, j in enumerate(self.theme.columns) if j[0] == name)
            fmt = self.theme.refid if isref else self.theme.columns[ind][-1]
            cols[ind].formatter.format = fmt
        return cols

    def addtodoc(self, _1, _2, src) -> List[Widget]: # type: ignore # pylint: disable=arguments-differ
        "creates the widget"
        cols  = self.__cols(self.__ctrl)
        self.__widget = DataTable(source         = src,
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = self.theme.colwidth*len(cols),
                                  height         = self.theme.height,
                                  name           = "Peaks:List")
        return [self.__widget]

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__widget].update(columns = self.__cols(self.__ctrl))

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
        self.__theme        = ctrl.theme.add(PeakIDPathTheme(), noerase = False)

    def _doresetmodel(self, ctrl):
        mdl  = self.__peaks.identification
        try:
            task = mdl.default(self.__peaks)
        except Exception as exc: # pylint: disable=broad-except
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

            finfo[1] = time # type: ignore
            if new:
                finfo[0] = path
                return

            if not diff:
                return

            self._doresetmodel(ctrl)

        doc.add_periodic_callback(_callback, self.__theme.filechecks)

    def observe(self, ctrl):
        "sets up observers"
        self.__dlg = FileDialog(ctrl, storage = 'constraints.path', filetypes = '*|xlsx')

    def addtodoc(self, mainview, ctrl, # type: ignore # pylint: disable=arguments-differ
                 *_) -> List[Widget]:
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


                track = ctrl.tasks.track(ctrl.display.get("tasks", "roottask"))
                dim   = track.instrument['dimension'] if track else 'µm'
                writecolumns(path, "Summary",
                             [('Bead',                  [self.__peaks.bead]),
                              ('Reference',             [self.__peaks.sequencekey]),
                              (f'Stretch (base/{dim})', [self.__peaks.stretch]),
                              (f'Bias ({dim})',         [self.__peaks.bias])])
                startfile(path)

            ctrl.display.update(
                self.__peaks.peaksmodel.display,
                constraintspath = str(Path(path).resolve())
            )
            self._doresetmodel(ctrl)

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

class DpxFitParams(Widget):
    "Interface to filters needed for cleaning"
    __css__            = route("peaksplot.css")
    __javascript__     = [ROUTE+"/jquery.min.js", ROUTE+"/jquery-ui.min.js"]
    __implementation__ = "_widget.coffee"
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
        self.__widget = DpxFitParams(**self.__data())

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
                fcn    = lambda x, y: np.around(x, self.RND[y]) if x else None
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
            self._fset = lambda i: ((ChiSquareFit, PeakGridFit)[i](),)
        else:
            self._fget = lambda i: getattr(i, attr)
            self._fset = lambda i: {attr: i}

    def getdefault(self, inst, usr = False):
        "returns the default value"
        ident = getattr(inst, '_model').identification
        return self._fget(ident.defaultattribute(self._name, usr))

    def __set_name__(self, _, name):
        self._attrname = name

    def __get__(self, inst, owner):
        return self if inst is None else self.getdefault(inst, True)

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

    def __get__(self,inst,owner)->bool:
        return not isinstance(getattr(inst,'_model').peakselection.task.finder,ByHistogram)

    def __set__(self,inst,value):
        mdl = getattr(inst,'_model')
        if value:
            mdl.peakselection.update(finder=FullEm(mincount=getattr(inst,"_eventcount")))
            return
        mdl.peakselection.update(finder=ByHistogram(mincount=getattr(inst,"_eventcount")))

def advanced(**kwa):
    "create the advanced button"
    msg  = ("<b>To fit to the baseline (singlestrand) peak, add '0'"
            " ('singlestrand') to the oligos.<b>")
    acc  = (
        BeadSubtractionModalDescriptor,
        AlignmentModalDescriptor,
        SingleStrandConfig,
        _IdAccessor
    )
    acc += tuple(kwa.get('accessors', ())) # type: ignore
    return tab(
        f"""
        ## Cleaning

        Discard z(∈ φ₅) < z(φ₁)-σ[HF]⋅α                    %(clipping.lowfactor).1oF
        %(BeadSubtractionModalDescriptor:)
        %(AlignmentModalDescriptor:)
        Discard the single strand peak (unless in oligos)  %(SingleStrandConfig:automated)b
        Detect and discard peaks below the baseline        %(baselinefilter.disabled)b

        ## Peaks

        {msg}

        {kwa.pop("peakstext", "")}
        Min frame count per hybridisation  %(eventdetection.events.select.minlength)D
        Min hybridisations per peak        %(peakselection.finder.grouper.mincount)D
        Re-align cycles using peaks        %(peakselection.align)b
        Peak kernel size (blank ⇒ auto)    %(peakselection.precision).4oF
        Exhaustive fit algorithm           %(_IdAccessor:alg)b
        Max Δ to theoretical peak          %(_IdAccessor:window)d
        """,
        accessors = {i.__name__: i for i in acc},
        figure    = kwa if kwa else (PeaksPlotTheme, PeaksPlotDisplay),
        base      = tab.taskwidget
    )

class PeaksPlotWidgets: # pylint: disable=too-many-instance-attributes
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

    def addtodoc(self, mainview, ctrl, doc, **kwa):
        "creates the widget"
        peaks = kwa.get('peaks', None)
        if peaks is None:
            peaks = getattr(mainview, "_src")['peaks']

        wdg    = {i: j.addtodoc(mainview, ctrl, peaks) for i, j in self.__dict__.items()}
        enable = dict(wdg)
        enable.pop('fitparams')
        self.enabler = TaskWidgetEnabler(enable)
        self.cstrpath.callbacks(ctrl, doc)
        if hasattr(mainview, '_hover'):
            self.seq.callbacks(getattr(mainview, '_hover'),
                               getattr(mainview, '_ticker'),
                               wdg['stats'][-1], wdg['peaks'][-1])
        self.advanced.callbacks(doc)
        return wdg, self.enabler

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
