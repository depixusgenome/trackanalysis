#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Cleaning beads"
from typing         import (Optional,   # pylint: disable=unused-import
                            List, Dict, Any, Type, TYPE_CHECKING)

import  bokeh.core.properties as props
from    bokeh           import layouts
from    bokeh.plotting  import Figure
from    bokeh.models    import (ColumnDataSource, DataTable, TableColumn,
                                Widget, StringFormatter, LayoutDOM, CustomJS)

import  numpy       as     np

from    view.base           import enableOnTrack
from    view.plots          import DpxNumberFormatter, WidgetCreator
from    eventdetection.view import AlignmentWidget
from    ._model             import DataCleaningModelAccess, DataCleaningTask

class CyclesListWidget(WidgetCreator):
    "Table containing stats per peaks"
    def __init__(self, model:DataCleaningModelAccess) -> None:
        super().__init__(model)
        self.__widget     = None # type: Optional[DataTable]
        css               = self.css.cycles.columns
        css.width.default = 60
        css.default       = [['population', u'% good',      '0.0'],
                             ['hfsigma',    'σ[HF]',        '0.0000'],
                             ['extent',     u'Δz',          '0.0'],
                             ['accepted',   u'Accepted',    '']]

    def create(self, _) -> List[Widget]:
        width = self.css.peaks.columns.width.get()
        get   = lambda i: self.css[i[4:]].get() if i.startswith('css:') else i
        fmt   = lambda i: (StringFormatter(text_align = 'center',
                                           font_style = 'bold') if i == '' else
                           DpxNumberFormatter(format = i, text_align = 'right'))
        cols  = list(TableColumn(field      = i[0],
                                 title      = get(i[1]),
                                 formatter  = fmt(i[2]))
                     for i in self.css.cycles.columns.get())

        self.__widget = DataTable(source      = ColumnDataSource(self.__data()),
                                  columns     = cols,
                                  editable    = False,
                                  row_headers = True,
                                  width       = width*len(cols),
                                  name        = "Cleaning:List")
        return [self.__widget]

    def reset(self, resets):
        "this widget has a source in common with the plots"
        itm  = self.__widget if resets is None else resets[self.__widget]
        data = self.__data()
        itm.update(data = data)

    def __data(self) -> dict:
        cache = self._model.datacleaning.cache
        if cache is None:
            return {i: [] for i, _1, _2 in self.css.cycles.get()}
        info     = {i: cache[i].values for i in ('hfsigma', 'extent', 'population')}
        info['accepted'] = np.ones(self._model.track.ncycles, dtype = 'bool')
        info['accepted'][self._model.datacleaning.badcycles] = False
        return info

class DpxCleaning(LayoutDOM):
    "This starts tests once flexx/browser window has finished loading"
    __implementation__ = "_cycles.coffee"
    framerate          = props.Float(30.)
    figure             = props.Instance(Figure)
    maxabsvalue        = props.Float(DataCleaningTask.maxabsvalue)
    maxderivate        = props.Float(DataCleaningTask.maxderivate)
    minpopulation      = props.Float(DataCleaningTask.minpopulation)
    minhfsigma         = props.Float(DataCleaningTask.minhfsigma)
    maxhfsigma         = props.Float(DataCleaningTask.maxhfsigma)
    minextent          = props.Float(DataCleaningTask.minextent)

class CleaningFilterWidget(WidgetCreator):
    "All inputs for cleaning"
    def __init__(self, model:DataCleaningModelAccess) -> None:
        super().__init__(model)
        self.__widget = None # type: Optional[DpxCleaning]

    def create(self, _) -> List[Widget]:
        self.__widget = DpxCleaning()
        return [self.__widget]

    def reset(self, resets):
        task = self._model.cleaning.task
        if task is None:
            task = self._model.cleaning.configtask

        info = {i:j for i, j in task.config() if hasattr(self.__widget, i)}
        info['framerate'] = getattr(self._model.track, 'framerate', 1./30.)
        (self.__widget if resets is None else resets[self.__widget]).update(**info)

    def setfigure(self, fig):
        "sets the figure"
        self.__widget.figure = fig
        fig.x_range.callback = CustomJS.from_coffeescript('mdl.onchangebounds()',
                                                          dict(mdl = self.__widget))

class WidgetMixin:
    "Everything dealing with changing the config"
    def __init__(self):
        self.__widgets = dict(table    = CyclesListWidget(self._model),
                              align    = AlignmentWidget(self._model),
                              cleaning = CleaningFilterWidget(self._model))

    def _widgetobservers(self):
        for widget in self.__widgets.values():
            widget.observe()

    def _createwidget(self, fig):
        widgets = {i: j.create(self.action) for i, j in self.__widgets.items()}
        self.__widgets['cleaning'].setfigure(fig)
        enableOnTrack(self, widgets)
        return layouts.widgetbox(widgets['align'], widgets['cleaning'], widgets['table'])

    def _resetwidget(self):
        for ite in self.__widgets.values():
            ite.reset(self._bkmodels)
