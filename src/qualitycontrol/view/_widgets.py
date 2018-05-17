#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing              import List, Dict
from    copy                import deepcopy

from    bokeh.models        import (ColumnDataSource, DataTable, TableColumn,
                                    Widget, StringFormatter, Div)
from    bokeh               import layouts

from    utils               import initdefaults
from    view.plots          import DpxNumberFormatter
from    ._model             import QualityControlModelAccess

_TEXT = """
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Cycles:</b></p></div>
    <div><p style='margin: 0px;'>{ncycles}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Beads:</b></p></div>
    <div><p style='margin: 0px;'>{nbeads} = {ngood} good + {nbad} bad</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width: 100px;'><b>Bad Beads:</b></p></div>
    <div><p style='margin: 0px;'>{listbad}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width: 100px'><b>Fixed Beads:</b></p></div>
    <div><p style='margin: 0px;'>{listfixed}</p></div>
</div>
<p></p>
""".strip().replace("    ", "").replace("\n", "")

class SummaryWidget:
    "summary info on the track"
    __widget: Div
    def __init__(self, model:QualityControlModelAccess) -> None:
        self.__tasks = model
        self.__model = {'text': _TEXT}

    def observe(self, ctrl):
        "do nothing"
        ctrl.theme.add("qcsummarywidget", {'text': self.__model})

    def addtodoc(self, _):
        "creates the widget"
        self.__widget = Div(text = self.__text())
        return [self.__widget]

    def reset(self, resets):
        "resets the widget"
        itm = self.__widget if resets is None else resets[self.__widget]
        txt = self.__text()
        itm.update(text = txt)

    def __text(self):
        track  = self.__tasks.track
        nbeads = 0  if track is None else sum(1 for i in track.beadsonly.keys())
        bad    = sorted(self.__tasks.badbeads())
        fixed  = sorted(self.__tasks.fixedbeads())
        return self.__model['text'].format(ncycles   = 0 if track is None else track.ncycles,
                                           nbeads    = nbeads,
                                           ngood     = nbeads - len(bad),
                                           nbad      = len(bad),
                                           listbad   = ', '.join(str(i) for i in bad),
                                           listfixed = ', '.join(str(i) for i in fixed))

class MessagesListWidgetTheme:
    "MessagesListWidgetTheme"
    height   = 500
    labels   = {'extent'     : 'Δz',
                'pingpong'   : 'Σ|dz|',
                'hfsigma'    : 'σ[HF]',
                'population' : '% good',
                'saturation' : 'non-closing'}
    columns  = [['bead',    u'Bead',    '0', 65],
                ['type',    u'Type',    '',  65],
                ['cycles',  u'Cycles',  '0', 65],
                ['message', u'Message', '',  65]]
    @initdefaults(frozenset(locals()))
    def __init__(self,**_):
        pass

class MessagesListWidget:
    "Table containing stats per peaks"
    __widget: DataTable
    __theme : MessagesListWidgetTheme
    def __init__(self, model:QualityControlModelAccess) -> None:
        self.__tasks = model

    def observe(self, ctrl):
        "do nothing"
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
        msgs = deepcopy(self.__tasks.messages())
        if len(msgs['bead']):
            trans = self.__theme.labels
            ncyc  = self.__tasks.track.ncycles
            msgs['cycles'] = [ncyc if i is None else i  for i in msgs['cycles']]
            msgs['type']   = [trans.get(i, i)           for i in msgs['type']]
        return {i: list(j) for i, j in msgs.items()}

class QualityControlWidgets:
    "All widgets"
    def __init__(self, mdl):
        self.messages = MessagesListWidget(mdl)
        self.summary  = SummaryWidget(mdl)

    def observe(self, ctrl):
        "observes the model"
        for widget in self.__dict__.values():
            widget.observe(ctrl)

    def reset(self, bkmodels):
        "resets the widgets"
        for widget in self.__dict__.values():
            widget.reset(bkmodels)

    def addtodoc(self, ctrl, mode):
        "returns all created widgets"
        get = lambda i: getattr(self, i).addtodoc(ctrl)
        return layouts.widgetbox(sum((get(i) for i in ('summary', 'messages')), []),
                                 **mode)
