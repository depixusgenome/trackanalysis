#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the fov data into a table"
import re
from   typing        import List
from   bokeh.models  import Div
from   bokeh.layouts import widgetbox
from   utils         import initdefaults
from   view.threaded import ThreadedDisplay, BaseModel

_BASE = """
        <div class='dpx-span'>
            <div><p style='margin: 0px; width:100px;'><b>%s</b></p></div>
            <div><p style='margin: 0px;'>{%s}</p></div>
        </div>
        """.strip().replace("\n", "").replace("    ", "").replace("    ", "").replace("    ", "")

_TEXT = "".join(_BASE % i for i in (("Magnet µm", "zmag:.3f"),
                                    ("Objective µm", "zobj:.3f"),
                                    ("X µm", "x:.3f"),
                                    ("Y µm", "y:.3f"),
                                    ("Sample °C", "tsample:.3f"),
                                    ("Box °C", "tsink:.3f"),
                                    ("Magnet °C", "tmagnet:.3f")))+"<p></p>"

class FoVTableTheme(BaseModel):
    "summary info on the field of view"
    name        = 'fovtable'
    template    = _TEXT
    refreshrate = 5
    width       = 120
    height      = 200
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class FoVTableView(ThreadedDisplay[FoVTableTheme]):
    "display summary info on the field of view"
    _FIND = re.compile(r'{(\w+)[:}]')
    def __init__(self, **_):
        super().__init__()
        self.__widget:  Div       = None
        self.__columns: List[str] = []
        self.__index              = 0

    def _addtodoc(self, ctrl, _):
        "creates the widget"
        self.__columns = [i for i in self._FIND.findall(self._model.template)]
        text           = self._model.template.format(**dict.fromkeys(self.__columns, 0.))

        mods = dict(width  = self._model.width,
                    height = self._model.height)
        self.__widget  = Div(text   = text, **mods)

        mods['sizing_mode'] = ctrl.theme.get('main', 'sizingmode', 'fixed')
        return [widgetbox(self.__widget, **mods)]

    def observe(self, ctrl):
        """
        add observers to the controller
        """
        if self._model in ctrl.theme:
            return

        ctrl.theme.add(self._model)
        ctrl.theme.observe(self._model, lambda **_: self.reset(ctrl))
        ctrl.daq.observe(self._onfovdata)

        @ctrl.daq.observe
        def _onupdatefov(old = None, **_): # pylint: disable=unused-variable
            if 'fov' in old:
                self.reset(ctrl)

    def _reset(self, control, cache):
        cache[self.__widget]['text'] = self.__data(control.data.fov)

    def _onfovdata(self, lines = None, **_):
        rate = self._model.refreshrate
        new  = self.__index + len(lines)
        if new // rate > self.__index // rate:
            text = self.__data(lines)
            self._doc.add_next_tick_callback(lambda: setattr(self.__widget, 'text', text))
        self.__index = new

    def __data(self, lines):
        return self._model.template.format(**{i: lines[-1][i] for  i in self.__columns})
