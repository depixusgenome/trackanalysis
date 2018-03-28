#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the fov data into a table"
import re
from   typing        import List
from   bokeh.models  import Div
from   utils         import initdefaults
from   view.threaded import ThreadedDisplay, BaseModel

_TEXT = """
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Magnet µm:</b></p></div>
    <div><p style='margin: 0px;'>{zmag}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Objective µm:</b></p></div>
    <div><p style='margin: 0px;'>{zobj}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>X µm:</b></p></div>
    <div><p style='margin: 0px;'>{x}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Y µm:</b></p></div>
    <div><p style='margin: 0px;'>{y}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Sample °C:</b></p></div>
    <div><p style='margin: 0px;'>{tsample}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Magnet °C:</b></p></div>
    <div><p style='margin: 0px;'>{tmagnet}</p></div>
</div>
<div class='dpx-span'>
    <div><p style='margin: 0px; width:100px;'><b>Sink °C:</b></p></div>
    <div><p style='margin: 0px;'>{tsink}</p></div>
</div>
<p></p>
""".strip().replace("    ", "").replace("\n", "")

class FoVTableTheme(BaseModel):
    "summary info on the field of view"
    name        = 'fovtable'
    template    = _TEXT
    refreshrate = 5
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

class FoVTableView(ThreadedDisplay[FoVTableTheme]):
    "display summary info on the field of view"
    _FIND = re.compile(r'{\w+}')
    def __init__(self, ctrl):
        super().__init__()
        self.__widget:  Div       = None
        self.__columns: List[str] = []
        self.__index              = 0
        if ctrl is not None:
            self.observe(ctrl)

    def _addtodoc(self, *_):
        "creates the widget"
        self.__columns = self._FIND.findall(self._model.template)
        text           = self._model.template.format(**dict.fromkeys(self.__columns, 0.))
        self.__widget  = Div(text = text)
        return [self.__widget]

    def observe(self, ctrl):
        """
        add observers to the controller
        """
        if self._model in ctrl.theme:
            return

        ctrl.theme.add(self._model)
        ctrl.theme.observe(self._model, lambda **_: self.reset(ctrl))
        ctrl.daq.observe(self._onaddfovlines)

        @ctrl.daq.observe
        def _onupdatefov(old = None, **_): # pylint: disable=unused-variable
            if 'fov' in old:
                self.reset(ctrl)

    def _reset(self, control, cache):
        cache[self.__widget]['text'] = self.__data(control.data.fov)

    def _onaddfovlines(self, lines = None, **_):
        rate = self._model.refreshrate
        new  = self.__index + len(lines)
        if new // rate > self.__index // rate:
            self.__widget.update(text = self.__data(lines))
        self.__index = new

    def __data(self, lines):
        return self._model.template.format(**{i: lines[-1][i] for  i in self.__columns})
