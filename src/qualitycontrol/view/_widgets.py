#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing              import List, Dict, Tuple, Iterable, Any
from    copy                import deepcopy

from    bokeh.models        import (ColumnDataSource, DataTable, TableColumn,
                                    Widget, Slider, StringFormatter, Div)
from    bokeh               import layouts
import  numpy               as     np

from    cleaning.names           import NAMES
from    taskcontrol.beadscontrol import TaskWidgetEnabler
from    utils                    import dataclass, dflt
from    utils.gui                import intlistsummary
from    view.plots               import DpxNumberFormatter
from    ._model                  import QualityControlModelAccess

def addtodoc(ctrl, theme, data) -> Tuple[Any, ColumnDataSource, DataTable]:
    "creates the widget"
    theme  = ctrl.theme.add(theme, False)
    src    = ColumnDataSource(data)
    fmt    = lambda x: (StringFormatter() if x == "" else
                        DpxNumberFormatter(format = x, text_align = 'right'))
    cols   = [TableColumn(field = i[0], title = i[1], width = i[2],
                          formatter = fmt(i[3]))
              for i in theme.columns]
    widget = DataTable(source         = src,
                       columns        = cols,
                       editable       = False,
                       index_position = None,
                       width          = sum(i[2] for i in theme.columns),
                       height         = theme.tableheight,
                       header_row     = theme.headers)
    return theme, src, widget

_TEXT = """
<table><tr>
    <td><b>Cycles:</b></td><td style="width:40px;">{ncycles}</td>
    <td><b>Beads:</b></td><td>{nbeads}</td>
</tr></table>
""".strip().replace("    ", "").replace("\n", "")

@dataclass
class QCSummaryTheme:
    "qc summary theme"
    name :  str = "qc.summary"
    text :  str = _TEXT
    height: int = 30

class SummaryWidget:
    "summary info on the track"
    __widget: Div
    def __init__(self, ctrl, model:QualityControlModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(QCSummaryTheme(), False)

    def addtodoc(self, *_):
        "creates the widget"
        self.__widget = Div(text = self.__text(), height = self.__theme.height)
        return [self.__widget]

    def reset(self, resets):
        "resets the widget"
        itm = self.__widget if resets is None else resets[self.__widget]
        txt = self.__text()
        itm.update(text = txt)

    def __text(self):
        track = self.__model.track
        if track is None:
            return self.__theme.text.format(ncycles = 0, nbeads = 0)
        return self.__theme.text.format(ncycles = track.ncycles,
                                        nbeads  = sum(1 for i in track.beads.keys()))

@dataclass
class QCBeadStatusTheme:
    "RampBeadStatusTheme"
    name:    str            = "qc.status"
    status:  Dict[str, str] = dflt({i: i for i in ("ok", "fixed", "bad", "missing")})
    tableheight:  int       = 80
    headers: bool           = False
    columns: List[List]     = dflt([["status",  "Status", 60, ""],
                                    ["count",   "Count",  40, "0"],
                                    ["percent", "(%)",    40, ""],
                                    ["beads",   "Beads",  180, ""]])
    def __post_init__(self):
        cols = self.columns[2] # pylint: disable=unsubscriptable-object
        if not self.headers:
            cols[-1] = ""
        elif cols[-1] == "":
            cols[-1] = "0"

class QCBeadStatusWidget:
    "Table containing beads per status"
    __widget: DataTable
    __src   : ColumnDataSource
    def __init__(self, ctrl, model, **args) -> None:
        self._model = model
        self.__theme = ctrl.theme.add(QCBeadStatusTheme(**args), False) # type: ignore
        if ctrl.theme.model("toolbar"):
            ctrl.theme.updatedefaults("toolbar", placeholder = '1, 2, ...? bad ?')

    def addtodoc(self, _, ctrl) -> List[Widget]:
        "creates the widget"
        self.__theme, self.__src, self.__widget = addtodoc(
            ctrl, self.__theme, self.__data()
        )
        return [self.__widget]

    def observe(self, _, ctrl):
        "observe the controller"
        @ctrl.display.observe
        def _onselectingbeads(text = "", accept = True, beads = None, **_):
            text = text.strip().lower()
            text = next((i for i, j in self.__theme.status.items()
                         if j.lower() == text), text)

            if text not in self.__theme.status:
                return

            beads.clear()
            data = self._data()
            if sum(sum(i) for i in data.values()) == 0:
                # not ready for processing
                beads.add(None)
                return

            if text == "bad" and not accept:
                for i, j in data.items():
                    if i != 'ok':
                        beads.update(j)
            else:
                beads.update(data[text])

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__src].update(data = self.__data())

    def __data(self):
        data    = self._data()
        status  = {"status":   list(self.__theme.status.values()),
                   "count":   [np.NaN]*len(self.__theme.status),
                   "percent": [np.NaN]*len(self.__theme.status),
                   "beads":   [""]*len(self.__theme.status)}

        for i, j in enumerate(self.__theme.status):
            beads              = data.get(j, [])
            status["beads"][i] = intlistsummary(beads)
            status["count"][i] = len(beads)

        cnt = 100./max(1, sum(status["count"]))
        if self.__theme.headers:
            status["percent"] = [i*cnt for i in status["count"]]
        else:
            status["percent"] = [f"{i*cnt:.0f} %" for i in status["count"]]
        return status

    def _data(self):
        return self._model.status()

@dataclass
class QCHairpinSizeTheme:
    "RampBeadStatusTheme"
    name:         str        = "qc.hairpinsize"
    title:        str        = "Hairpins bin size"
    binsize:      float      = .1
    binstart:     float      = .05
    binend:       float      = 1.
    binstep:      float      = .05
    headers:      bool       = False
    tableheight:  int        = 125
    sliderheight: int        = 48
    columns:      List[List] = dflt([
        ["z",       "Δz (µm)", 60, ""],
        ["count",   "Count",   40, "0"],
        ["percent", "(%)",     40, ""],
        ["beads",   "Beads",  180, ""]
    ])
    def __post_init__(self):
        # pylint: disable=unsubscriptable-object
        cols = self.columns
        if not self.headers:
            cols[2][-1] = cols[0][-1] = ""
        else:
            if cols[2][-1] == "":
                cols[2][-1] = "0"
            if cols[0][-1] == "":
                cols[2][-1] = "0.00"

class QCHairpinSizeWidget:
    "Table containing discrete bead extensions"
    __table : DataTable
    __slider: Slider
    __src   : ColumnDataSource
    def __init__(self, ctrl, model):
        self._model = model
        self._theme = ctrl.theme.add(QCHairpinSizeTheme(), False)

    def addtodoc(self, mainview, ctrl) -> List[Widget]:
        "creates the widget"
        self._theme, self.__src, self.__table = addtodoc(ctrl,
                                                         self._theme,
                                                         self.__tabledata())
        self.__slider = Slider(title  = self._theme.title,
                               step   = self._theme.binstep,
                               height = self._theme.sliderheight,
                               **self.__sliderdata())

        @mainview.actionifactive(ctrl)
        def _onchange_cb(attr, old, new):
            ctrl.theme.update(self._theme, binsize = new)
        self.__slider.on_change("value", _onchange_cb)
        return [self.__slider, self.__table]

    def observe(self, mainview, ctrl):
        "observe the controller"
        @ctrl.theme.observe(self._theme)
        def _observe(**_):
            if mainview.isactive():
                self.__slider.update(**self.__sliderdata())
                self.__src.update(data = self.__tabledata())

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__src].update(data = self.__tabledata())
        resets[self.__slider].update(**self.__sliderdata())

    def _sliderdata(self) -> Dict[str, float]:
        return {'start': self._theme.binstart, "end"  : self._theme.binend}

    def _tabledata(self) -> Iterable[Tuple[int, float]]:
        track = self._model.track
        if track is None:
            return ()
        return ((i, track.beadextension(i)) for i in  self._model.status()["ok"])

    def __sliderdata(self) -> Dict[str, float]:
        data = self._sliderdata()
        data["value"] = self._theme.binsize
        return data

    def __tabledata(self) -> Dict[str, np.ndarray]:
        out   = {'z': np.empty(0), 'count': np.empty(0), 'percent': np.empty(0)}
        data  = np.array(list(self._tabledata()),
                         dtype = [("bead", "i4"), ("extent", "f4")])
        if len(data) == 0:
            return out

        bsize = self._theme.binsize
        inds  = np.round(data["extent"]/bsize).astype(int)
        izval = np.sort(np.unique(inds))
        if len(izval):
            cnt = np.array([np.sum(inds == i) for i in izval])
            out.update(z       = [data["extent"][inds == i].mean() for i in izval],
                       count   = cnt,
                       percent = cnt* 100./cnt.sum(),
                       beads   = [intlistsummary(data["bead"][inds == i])
                                  for i in izval])
        if not self._theme.headers:
            out["percent"] = [f"{i:.0f} %"  for i in out["percent"]]
            out["z"]       = [f"{i:.2f} µm" for i in out["z"]]
        return out

@dataclass
class MessagesListWidgetTheme:
    "MessagesListWidgetTheme"
    name    : str = "qc.messages"
    height  : int = 150
    labels  : Dict[str, str] = dflt(NAMES)
    columns : List[List]     = dflt([['bead',    u'Bead',    '0', 65],
                                     ['type',    u'Type',    '',  (320-65)//3],
                                     ['cycles',  u'Cycles',  '0', (320-65)//3],
                                     ['message', u'Message', '',  (320-65)//3]])

class MessagesListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    __theme : MessagesListWidgetTheme
    def __init__(self, ctrl, model:QualityControlModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(MessagesListWidgetTheme())

    def addtodoc(self, *_) -> List[Widget]:
        "creates the widget"
        fmt   = lambda i: (StringFormatter() if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = i[1],
                                 formatter  = fmt(i[2]),
                                 width      = i[3])
                     for i in self.__theme.columns)

        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = sum([i[-1] for i in self.__theme.columns]),
                                  height         = self.__theme.height,
                                  name           = "Messages:List")
        return [self.__widget]

    def reset(self, resets):
        "resets the widget"
        itm  = self.__widget.source if resets is None else resets[self.__widget.source]
        itm.update(data = self.__data())

    def shoulddisable(self) -> bool:
        "whether one can enable the widget"
        return self.__model.track is None

    def __data(self) -> Dict[str, List]:
        msgs = deepcopy(self.__model.messages())
        if len(msgs['bead']):
            trans = self.__theme.labels
            ncyc  = self.__model.track.ncycles if self.__model.track is not None else 1
            msgs['cycles'] = [ncyc if i is None else i  for i in msgs['cycles']]
            msgs['type']   = [trans.get(i, i)           for i in msgs['type']]
        return {i: list(j) for i, j in msgs.items()}

class QualityControlWidgets:
    "All widgets"
    __objects : TaskWidgetEnabler
    def __init__(self, ctrl, mdl):
        self.summary  = SummaryWidget(ctrl, mdl)
        self.status   = QCBeadStatusWidget(ctrl, mdl)
        self.extent   = QCHairpinSizeWidget(ctrl, mdl)
        self.messages = MessagesListWidget(ctrl, mdl)

    def reset(self, bkmodels):
        "resets the widgets"
        for name, widget in self.__dict__.items():
            if name[0] != "_":
                widget.reset(bkmodels)
        self.__objects.disable(bkmodels, self.messages.shoulddisable())

    def observe(self, mainview, ctrl):
        "observe the controller"
        for name, widget in self.__dict__.items():
            if name[0] != "_":
                getattr(widget, "observe", lambda *x: None)(mainview, ctrl)

    def addtodoc(self, mainview, ctrl, mode):
        "returns all created widgets"
        get     = lambda i: getattr(self, i).addtodoc(mainview, ctrl)
        order   = "summary", "status", "extent", "messages"
        widgets = layouts.widgetbox(sum((get(i) for i in order), []), **mode)
        self.__objects = TaskWidgetEnabler(widgets)
        return widgets
