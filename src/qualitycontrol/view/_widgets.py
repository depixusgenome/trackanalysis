#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing              import List, Dict
from    copy                import deepcopy

from    bokeh.models        import (ColumnDataSource, DataTable, TableColumn,
                                    Widget, StringFormatter, Div)
from    bokeh               import layouts
import  numpy               as     np

from    utils               import dataclass, dflt
from    utils.array         import intlistsummary
from    view.plots          import DpxNumberFormatter
from    ._model             import QualityControlModelAccess

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

    def addtodoc(self, _):
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
    name:    str            = "ramp.status"
    status:  Dict[str, str] = dflt({i: i for i in ("ok", "fixed", "bad", "missing")})
    height:  int            = 120
    headers: bool           = False
    columns: List[List]     = dflt([["status",  "Status", 60, ""],
                                    ["count",   "Count",  40, "0"],
                                    ["percent", "(%)",    40, ""],
                                    ["beads",   "Beads",  180, ""]])

class QCBeadStatusWidget:
    "Table containing beads per status"
    __widget: DataTable
    __src   : ColumnDataSource
    def __init__(self, ctrl, model:QualityControlModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(QCBeadStatusTheme())

    def addtodoc(self, *_) -> List[Widget]:
        "creates the widget"
        self.__src = ColumnDataSource(self.__data())
        fmt        = lambda x: (StringFormatter() if x == "" else
                                DpxNumberFormatter(format = x, text_align = 'right'))
        cols       = [TableColumn(field = i[0], title = i[1], width = i[2],
                                  formatter = fmt(i[3]))
                      for i in self.__theme.columns]
        self.__widget = DataTable(source         = self.__src,
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = sum(i[2] for i in self.__theme.columns),
                                  height         = self.__theme.height,
                                  header_row     = self.__theme.headers,
                                  name           = "QC:Status")
        return [self.__widget]

    def observe(self, ctrl):
        "observe the controller"

    def reset(self, resets):
        "resets the wiget when a new file is opened"
        resets[self.__src].update(data = self.__data())

    def __data(self):
        data    = self.__model.status()
        status  = {"status":   list(self.__theme.status.values()),
                   "count":   [np.NaN]*len(self.__theme.status),
                   "percent": [np.NaN]*len(self.__theme.status),
                   "beads":   [""]*len(self.__theme.status)}

        for i, j in enumerate(self.__theme.status):
            beads              = data.get(j, [])
            status["beads"][i] = intlistsummary(beads)
            status["count"][i] = len(beads)

        cnt               = 100./max(1, sum(status["count"]))
        status["percent"] = [f"{i*cnt:.0f} %" for i in status["count"]]
        return status

@dataclass
class MessagesListWidgetTheme:
    "MessagesListWidgetTheme"
    name     : str = "qc.messages"
    height   : int = 400
    labels   : Dict[str, str] = dflt({'extent'     : 'Δz',
                                      'pingpong'   : 'Σ|dz|',
                                      'hfsigma'    : 'σ[HF]',
                                      'population' : '% good',
                                      'saturation' : 'non-closing'})
    columns : List[List]      = dflt([['bead',    u'Bead',    '0', 65],
                                      ['type',    u'Type',    '',  78],
                                      ['cycles',  u'Cycles',  '0', 78],
                                      ['message', u'Message', '',  78]])

class MessagesListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    __theme : MessagesListWidgetTheme
    def __init__(self, ctrl, model:QualityControlModelAccess) -> None:
        self.__model = model
        self.__theme = ctrl.theme.add(MessagesListWidgetTheme())

    def addtodoc(self, _) -> List[Widget]:
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
    def __init__(self, ctrl, mdl):
        self.messages = MessagesListWidget(ctrl, mdl)
        self.summary  = SummaryWidget(ctrl, mdl)
        self.status   = QCBeadStatusWidget(ctrl, mdl)

    def reset(self, bkmodels):
        "resets the widgets"
        for widget in self.__dict__.values():
            widget.reset(bkmodels)

    def addtodoc(self, ctrl, mode):
        "returns all created widgets"
        get   = lambda i: getattr(self, i).addtodoc(ctrl)
        order = "summary", "status", "messages"
        return layouts.widgetbox(sum((get(i) for i in order), []), **mode)
