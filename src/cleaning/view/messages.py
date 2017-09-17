#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"View module showing all messages concerning discarded beads"
from    typing             import List, Dict, cast, TYPE_CHECKING

from    bokeh.models       import (ColumnDataSource, DataTable, TableColumn,
                                   Widget, StringFormatter)
from    bokeh.layouts      import widgetbox

from    view.plots         import DpxNumberFormatter, WidgetCreator, PlotView
from    view.plots.tasks   import TaskPlotCreator, TaskPlotModelAccess, TaskAccess
from    ..processor        import DataCleaningTask, DataCleaningProcessor

class GuiDataCleaningProcessor(DataCleaningProcessor):
    "gui data cleaning processor"
    tasktype = DataCleaningProcessor.tasktype
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

    def messages(self) -> Dict[str, List]:
        "returns beads and warnings where applicable"
        default = dict(type = [], message = [], bead = []) # type: Dict[str, List]
        tsk     = self.cleaning.task
        if tsk is None:
            return default

        ctrl = self.processors(GuiDataCleaningProcessor)
        if ctrl is None:
            return default

        for _ in next(iter(ctrl.run(copy = True))):
            pass

        mem = ctrl.data.getCache(tsk)().pop('messages', None)
        if mem is None:
            return default

        return dict(bead    = [i[0] for i in mem],
                    cycles  = [i[1] for i in mem],
                    type    = [i[2] for i in mem],
                    message = [i[3] for i in mem])

class MessagesListWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:MessagesModelAccess) -> None:
        super().__init__(model)
        self.__widget: DataTable   = None
        css                        = self.__config
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
                                  name        = "Messages:List")
        return [self.__widget]

    def reset(self, resets):
        "this widget has a source in common with the plots"
        itm  = self.__widget.source if resets is None else resets[self.__widget.source]
        data = self.__data()
        itm.update(data = data)

    def __data(self) -> Dict[str, List]:
        mdl   = cast(MessagesModelAccess, self._model)
        msgs  = mdl.messages()
        if len(msgs['bead']):
            trans = self.__config.type.getitems(...)
            ncyc  = mdl.track.ncycles
            msgs['cycles'] = [ncyc if i is None else i  for i in msgs['cycles']]
            msgs['type']   = [trans.get(i, i)           for i in msgs['type']]
        return msgs

class MessagesPlotCreator(TaskPlotCreator):
    "Creates plots for discard list"
    _MODEL = MessagesModelAccess # type: ignore
    def __init__(self, *args):
        super().__init__(*args)
        self._widgets = dict(messages = MessagesListWidget(self._model))
        if TYPE_CHECKING:
            self._model = MessagesModelAccess(self)

    def observe(self):
        super().observe()
        for widget in self._widgets.values():
            widget.observe()

    def _create(self, doc):
        "returns the figure"
        return widgetbox(self._widgets['messages'].create(self.action))

    def _reset(self):
        for widget in self._widgets.values():
            widget.reset(self._bkmodels)

class MessagesView(PlotView):
    "a widget with all discards messages"
    PLOTTER = MessagesPlotCreator
    def ismain(self):
        "Cleaning and alignment, ... are set-up by default"
        super()._ismain(tasks  = ['datacleaning', 'extremumalignment'],
                        ioopen = [slice(None, -2),
                                  'control.taskio.ConfigGrFilesIO',
                                  'control.taskio.ConfigTrackIO'])
