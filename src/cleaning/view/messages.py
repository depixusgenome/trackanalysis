#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing              import List, Dict, Set, cast
from    copy                import deepcopy

from    bokeh.models        import (ColumnDataSource, DataTable, TableColumn,
                                    Widget, StringFormatter, Div)
from    bokeh.layouts       import widgetbox

from    data                import BEADKEY
from    view.plots          import DpxNumberFormatter, WidgetCreator, PlotView
from    view.plots.tasks    import TaskPlotCreator
from    control.modelaccess import TaskPlotModelAccess, TaskAccess
from    ..processor         import DataCleaningTask, DataCleaningProcessor

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    @staticmethod
    def canregister():
        "allows discarding some specific processors from automatic registration"
        return False

    @classmethod
    def compute(cls, frame, info, cache = None, **cnf):
        "returns the result of the beadselection"
        err = super().compute(frame, info, cache = cache, **cnf)
        if err:
            cache.setdefault('messages', []).extend([(info[0],)+ i for i in err.args[0].data()])
        return None

class MessagesModelAccess(TaskPlotModelAccess):
    "access to data cleaning"
    def __init__(self, ctrl, key: str = None) -> None:
        super().__init__(ctrl, key)
        self.cleaning   = TaskAccess(self, DataCleaningTask)
        self.__messages = self.project.messages
        self.__messages.setdefault(None)

    def buildmessages(self):
        "creates beads and warnings where applicable"
        default = dict.fromkeys(('type', 'message', 'bead', 'cycles'), []) # type: Dict[str, List]
        tsk     = self.cleaning.task
        if tsk is not None:
            ctrl = self.processors(GuiDataCleaningProcessor)
            if ctrl is not None:
                for _ in next(iter(ctrl.run(copy = True))):
                    pass

                mem = ctrl.data.getCache(tsk)().pop('messages', None)
                if mem is not None:
                    default = dict(bead    = [i[0] for i in mem],
                                   cycles  = [i[1] for i in mem],
                                   type    = [i[2] for i in mem],
                                   message = [i[3] for i in mem])
        self.__messages.set(default)

    def badbeads(self) -> Set[BEADKEY]:
        "returns bead ids with messages"
        return set(self.messages()['bead'])

    def messages(self) -> Dict[str, List]:
        "returns beads and warnings where applicable"
        msg = self.__messages.get()
        if msg is None:
            self.buildmessages()
        return self.__messages.get()

    def clear(self):
        "clears the model's cache"
        self.__messages.pop()

class SummaryWidget(WidgetCreator[MessagesModelAccess]):
    "summary info on the track"
    def __init__(self, model:MessagesModelAccess) -> None:
        super().__init__(model)
        self.__widget: Div = None

    def create(self, _):
        "creates the widget"
        self.__widget = Div()
        return [self.__widget]

    def reset(self, resets):
        "resets the widget"
        itm = self.__widget if resets is None else resets[self.__widget]
        txt = self.__text()
        itm.update(text = txt)

    def __text(self):
        track = self._model.track
        if track is None:
            return ''

        nbeads = sum(1 for i in track.beadsonly.keys())
        beads  = sorted(self._model.badbeads())
        txt    = ("<div class='dpx-span'><div>"
                  "<p>Number of cycles:</p>"
                  "<p>Number of beads:</p>"
                  "<p>Bad beads:</p>"
                  "</div><div>"
                  f"<p>{track.ncycles}</p>"
                  f"<p>{nbeads}</p>"
                  f"<p>{len(beads)}=[{', '.join(str(i) for i in beads)}]</p>"
                  "</div></div>")
        return txt

class MessagesListWidget(WidgetCreator[MessagesModelAccess]):
    "Table containing stats per peaks"
    def __init__(self, model:MessagesModelAccess) -> None:
        super().__init__(model)
        self.__widget: DataTable   = None
        css                        = self.__config
        css.height.default   = 500
        css.type.defaults    = {'extent'     : 'Δz',
                                'hfsigma'    : 'σ[HF]',
                                'population' : '% good'}
        css.columns.default  = [['bead',    u'Bead',    '0', 65],
                                ['type',    u'Type',    '',  65],
                                ['cycles',  u'Cycles',  '0', 65],
                                ['message', u'Message', '',  250]]

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

        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = False,
                                  row_headers = False,
                                  width       = sum([i[-1] for i in cnf.get()]),
                                  height      = self.__config.height.get(),
                                  name        = "Messages:List")
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
        mdl   = cast(MessagesModelAccess, self._model)
        msgs  = deepcopy(mdl.messages())
        if len(msgs['bead']):
            trans = self.__config.type.getitems(...)
            ncyc  = mdl.track.ncycles
            msgs['cycles'] = [ncyc if i is None else i  for i in msgs['cycles']]
            msgs['type']   = [trans.get(i, i)           for i in msgs['type']]
        return {i: list(j) for i, j in msgs.items()}

class MessagesPlotCreator(TaskPlotCreator[MessagesModelAccess]):
    "Creates plots for discard list"
    _RESET = frozenset()         # type: frozenset
    def __init__(self, *args):
        super().__init__(*args)
        self._widgets = dict(messages = MessagesListWidget(self._model),
                             summary  = SummaryWidget(self._model))

    def observe(self):
        "observes the model"
        super().observe()
        for widget in self._widgets.values():
            widget.observe()

    def _create(self, _):
        "returns the figure"
        act   = self.action
        order = 'summary', 'messages'
        get   = lambda i: self._widgets[i].create(act)
        lst   = sum((get(i) for i in order), [])
        return widgetbox(lst)

    def _reset(self):
        for widget in self._widgets.values():
            widget.reset(self._bkmodels)

class MessagesView(PlotView[MessagesPlotCreator]):
    "a widget with all discards messages"
    def ismain(self):
        "Cleaning and alignment, ... are set-up by default"
        super()._ismain(tasks  = ['datacleaning', 'extremumalignment'],
                        ioopen = [slice(None, -2),
                                  'control.taskio.ConfigGrFilesIO',
                                  'control.taskio.ConfigTrackIO'])
