#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the bead characteristics"
from   bokeh.layouts import widgetbox
from   bokeh.models  import (DataTable, TableColumn, ColumnDataSource,
                             NumberFormatter)

from   utils         import initdefaults
from   view.threaded import ThreadedDisplay, BaseModel
from   .model        import DAQBead

class BeadsTableTheme(BaseModel):
    "summary info on the field of view"
    name        = 'beadstable'
    width       = 80
    height      = 200
    columns     = [['x', 'X (µm)',      '0.0'],
                   ['y', 'Y (µm)',      '0.0'],
                   ['w', 'Width (µm)',  '0.000'],
                   ['h', 'Height (µm)', '0.000']]
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class BeadsTableView(ThreadedDisplay[BeadsTableTheme]):
    "display summary info on the field of view"
    def __init__(self, ctrl, **_):
        super().__init__()
        self._widget:  DataTable        = None
        self._source:  ColumnDataSource = None
        if ctrl is not None:
            self.observe(ctrl)

    def _addtodoc(self, ctrl, _):
        "creates the widget"
        self._source = ColumnDataSource(data = self.__data(ctrl))
        cols  = self.__columns(ctrl)
        self._widget = DataTable(source   = self._source,
                                 columns  = cols,
                                 editable = False,
                                 width    = self._model.width*len(cols),
                                 height   = self._model.height,
                                 name     = "Beads:List")
        mods = dict(sizing_mode = ctrl.theme.get('main', 'sizingmode', 'fixed'),
                    width       = self._model.width*(len(cols)+1),
                    height      = self._model.height)
        return [widgetbox(self._widget, **mods)]

    def observe(self, ctrl):
        """
        add observers to the controller
        """
        if self._model in ctrl.theme:
            return

        ctrl.theme.add(self._model)
        ctrl.theme.observe(self._model, lambda **_: self.reset(ctrl))

        @ctrl.daq.observe("addbeads", "removebeads", "updatebeads")
        def _onbeads(**_): # pylint: disable=unused-variable
            self.reset(ctrl)

        @ctrl.daq.observe
        def _onlisten(**_): # pylint: disable=unused-variable
            tmp = dict(self._source.data)
            tmp.clear()
            self._source.data = tmp

    def _reset(self, ctrl, cache):
        cache[self.__widget]['text'] = self.__data(ctrl)

    def __columns(self, _):
        return [TableColumn(field     = i[0],
                            title     = i[1],
                            formatter = NumberFormatter(format = i[2]))
                for i in self._model.columns]

    @staticmethod
    def __data(ctrl):
        return DAQBead.todict(ctrl.daq.config.beads)
