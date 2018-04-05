#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cleaning beads"
from    typing          import List
from    abc             import ABC

import  bokeh.core.properties as props
from    bokeh.plotting  import Figure
from    bokeh.models    import (ColumnDataSource, DataTable, TableColumn,
                                Widget, StringFormatter, CustomJS)

import  numpy       as     np

from    utils.gui           import parseints
from    view.base           import enableOnTrack
from    view.static         import ROUTE
from    view.plots          import DpxNumberFormatter, WidgetCreator
from    eventdetection.view import AlignmentWidget
from    ._model             import DataCleaningModelAccess, DataCleaningTask

class CyclesListWidget(WidgetCreator[DataCleaningModelAccess]):
    "Table containing stats per peaks"
    def __init__(self, model:DataCleaningModelAccess) -> None:
        super().__init__(model)
        self.__widget: DataTable  = None
        css                       = self.__config
        css.lines.order.default   = ('population', 'hfsigma', 'extent', 'aberrant',
                                     'saturation', 'good')
        css.columns.width.default = 65
        css.height.default        = 500
        css.columns.default       = [['cycle',      u'Cycle',     '0'],
                                     ['population', u'% good',    '0.'],
                                     ['hfsigma',    u'σ[HF]',     '0.0000'],
                                     ['extent',     u'Δz',        '0.0'],
                                     ['saturation', u'Non-closing', ''],
                                     ['discarded',  u'Discarded', '']]

    @property
    def __config(self):
        return self.css.table

    def create(self, _) -> List[Widget]:
        "creates the widget"
        cnf   = self.__config.columns
        width = cnf.width.get()
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        fmt   = lambda i: (StringFormatter(text_align = 'center',
                                           font_style = 'bold') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = get(i[1]),
                                 formatter  = fmt(i[2]))
                     for i in cnf.get())

        self.__widget = DataTable(source         = ColumnDataSource(self.__data()),
                                  columns        = cols,
                                  editable       = False,
                                  index_position = None,
                                  width          = width*len(cols),
                                  height         = self.__config.height.get(),
                                  name           = "Cleaning:List")
        return [self.__widget]

    def reset(self, resets):
        "this widget has a source in common with the plots"
        itm  = self.__widget.source if resets is None else resets[self.__widget.source]
        data = self.__data()
        itm.update(data = data)

    def __data(self) -> dict:
        cache = self._model.cleaning.cache
        if cache is None or len(cache) == 0:
            return {i: [] for i, _1, _2 in self.__config.columns.get()}
        names = set(i[0] for i in self.__config.columns.get()) & set(cache)
        bad   = self._model.cleaning.nbadcycles(cache)
        order = self._model.cleaning.sorted(self.__config.lines.order.get(), cache)
        info  = {i: cache[i].values[order] for i in names}

        info['saturation'] = np.zeros(len(order), dtype = 'U1')
        info['discarded']  = np.zeros(len(order), dtype = 'U1')
        if len(cache['saturation'].max):
            info['saturation'][cache['saturation'].max] = '✗'
            info['discarded'][:]                        = '✗'
        else:
            info['discarded'][:bad]                     = '✗'

        info['cycle'] = order
        return info

class DpxCleaning(Widget):
    "Interface to filters needed for cleaning"
    __css__            = ROUTE+"/cleaning.css"
    __javascript__     = [ROUTE+"/jquery.min.js", ROUTE+"/jquery-ui.min.js"]
    __implementation__ = "_widget.coffee"
    frozen             = props.Bool(True)
    framerate          = props.Float(30.)
    figure             = props.Instance(Figure)
    subtracted         = props.String("")
    subtractcurrent    = props.Int(0)
    maxabsvalue        = props.Float(DataCleaningTask.maxabsvalue)
    maxderivate        = props.Float(DataCleaningTask.maxderivate)
    minpopulation      = props.Float(DataCleaningTask.minpopulation)
    minhfsigma         = props.Float(DataCleaningTask.minhfsigma)
    maxhfsigma         = props.Float(DataCleaningTask.maxhfsigma)
    minextent          = props.Float(DataCleaningTask.minextent)
    maxextent          = props.Float(DataCleaningTask.maxextent)
    maxsaturation       = props.Float(DataCleaningTask.maxsaturation)

class CleaningFilterWidget(WidgetCreator[DataCleaningModelAccess]):
    "All inputs for cleaning"
    def __init__(self, model:DataCleaningModelAccess) -> None:
        super().__init__(model)
        self.__widget: DpxCleaning = None

    def create(self, action) -> List[Widget]:
        "creates the widget"
        self.__widget = DpxCleaning(name = "Cleaning:Filter")

        @action
        def _on_cb(attr, old, new):
            self._model.cleaning.update(**{attr: new})

        for name in ('maxabsvalue', 'maxderivate', 'minpopulation',
                     'minhfsigma',  'maxhfsigma',  'minextent',
                     'maxsaturation'):
            self.__widget.on_change(name, _on_cb)

        @action
        def _on_subtract_cb(attr, old, new):
            self._model.subtracted.beads = parseints(new)
        self.__widget.on_change('subtracted', _on_subtract_cb)

        @action
        def _on_subtract_cur_cb(attr, old, new):
            self._model.subtracted.switch(self._model.bead)
        self.__widget.on_change('subtractcurrent', _on_subtract_cur_cb)

        return [self.__widget]

    def reset(self, resets):
        "resets the widget when opening a new file, ..."
        task = self._model.cleaning.task
        if task is None:
            task = self._model.cleaning.configtask

        info = {i:j for i, j in task.config().items() if hasattr(self.__widget, i)}

        info['framerate'] = getattr(self._model.track, 'framerate', 1./30.)
        info['subtracted']= ', '.join(str(i) for i in sorted(self._model.subtracted.beads))

        (self.__widget if resets is None else resets[self.__widget]).update(**info)

    def setfigure(self, fig):
        "sets the figure"
        self.__widget.figure = fig
        fig.x_range.callback = CustomJS.from_coffeescript('mdl.onchangebounds()',
                                                          dict(mdl = self.__widget))

class WidgetMixin(ABC):
    "Everything dealing with changing the config"
    def __init__(self):
        align = AlignmentWidget[DataCleaningModelAccess](self._model)
        self.__widgets = dict(table    = CyclesListWidget(self._model),
                              align    = align,
                              cleaning = CleaningFilterWidget(self._model))

    def _widgetobservers(self):
        for widget in self.__widgets.values():
            widget.observe()

    def _createwidget(self, fig):
        widgets = {i: j.create(self.action) for i, j in self.__widgets.items()}
        self.__widgets['cleaning'].setfigure(fig)
        enableOnTrack(self, widgets)
        return widgets

    def _resetwidget(self):
        for ite in self.__widgets.values():
            ite.reset(self._bkmodels)
