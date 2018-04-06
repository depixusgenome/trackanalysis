#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing              import List, Dict, cast
from    copy                import deepcopy

from    bokeh.models        import (ColumnDataSource, DataTable, TableColumn,
                                    Widget, StringFormatter, Div)
from    bokeh               import layouts

from    view.plots          import DpxNumberFormatter, WidgetCreator
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

class SummaryWidget(WidgetCreator[QualityControlModelAccess]):
    "summary info on the track"
    def __init__(self, model:QualityControlModelAccess) -> None:
        super().__init__(model)
        self.__widget: Div = None
        self.css.text.default = _TEXT

    def create(self, _):
        "creates the widget"
        self.__widget = Div(text = self.__text())
        return [self.__widget]

    def reset(self, resets):
        "resets the widget"
        itm = self.__widget if resets is None else resets[self.__widget]
        txt = self.__text()
        itm.update(text = txt)

    def __text(self):
        track  = self._model.track
        nbeads = 0  if track is None else sum(1 for i in track.beadsonly.keys())
        bad    = sorted(self._model.badbeads())
        fixed  = sorted(self._model.fixedbeads())
        return self.css.text.format(ncycles   = 0 if track is None else track.ncycles,
                                    nbeads    = nbeads,
                                    ngood     = nbeads - len(bad),
                                    nbad      = len(bad),
                                    listbad   = ', '.join(str(i) for i in bad),
                                    listfixed = ', '.join(str(i) for i in fixed))

class MessagesListWidget(WidgetCreator[QualityControlModelAccess]):
    "Table containing stats per peaks"
    def __init__(self, model:QualityControlModelAccess) -> None:
        super().__init__(model)
        self.__widget: DataTable   = None
        css                        = self.__config
        css.height.default   = 500
        css.type.defaults    = {'extent'     : 'Δz',
                                'pingpong'   : 'Σ|dz|',
                                'hfsigma'    : 'σ[HF]',
                                'population' : '% good',
                                'saturation' : 'non-closing'}
        css.columns.default  = [['bead',    u'Bead',    '0', 65],
                                ['type',    u'Type',    '',  65],
                                ['cycles',  u'Cycles',  '0', 65],
                                ['message', u'Message', '',  65]]

    @property
    def __config(self):
        return self.css.table

    def create(self, _) -> List[Widget]:
        "creates the widget"
        cnf   = self.__config.columns
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        fmt   = lambda i: (StringFormatter() if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = get(i[1]),
                                 formatter  = fmt(i[2]),
                                 width      = i[3])
                     for i in cnf.get())

        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = sum([i[-1] for i in cnf.get()]),
                                  height         = self.__config.height.get(),
                                  name           = "Messages:List")
        return [self.__widget]

    def reset(self, resets):
        "resets the widget"
        itm  = self.__widget.source if resets is None else resets[self.__widget.source]
        itm.update(data = self.__data())

        # bug in bokeh 0.12.9: table update is incorrect unless the number
        # of rows is fixed
        width = sum([i[-1] for i in self.__config.columns.get()])
        if width == self.__widget.width:
            width = width+1
        resets[self.__widget].update(width = width)

    def __data(self) -> Dict[str, List]:
        mdl   = cast(QualityControlModelAccess, self._model)
        msgs  = deepcopy(mdl.messages())
        if len(msgs['bead']):
            trans = self.__config.type.getitems(...)
            ncyc  = mdl.track.ncycles
            msgs['cycles'] = [ncyc if i is None else i  for i in msgs['cycles']]
            msgs['type']   = [trans.get(i, i)           for i in msgs['type']]
        return {i: list(j) for i, j in msgs.items()}

class QualityControlWidgets:
    "All widgets"
    def __init__(self, mdl):
        self.messages = MessagesListWidget(mdl)
        self.summary  = SummaryWidget(mdl)

    def observe(self):
        "observes the model"
        for widget in self.__dict__.values():
            widget.observe()

    def reset(self, bkmodels):
        "resets the widgets"
        for widget in self.__dict__.values():
            widget.reset(bkmodels)

    def create(self, action, mode):
        "returns all created widgets"
        get = lambda i: getattr(self, i).create(action)
        return layouts.widgetbox(sum((get(i) for i in ('summary', 'messages')), []),
                                 **mode)
