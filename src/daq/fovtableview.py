#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the fov data into a table"
import re
from   bokeh.models  import Div

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

class FoVTableModel:
    "summary info on the field of view"
    template    = _TEXT
    refreshrate = 5

class FoVTableWidget:
    "display summary info on the field of view"
    def __init__(self):
        self._model        = FoVTableModel()
        self.__widget: Div = None
        self.__columns     = re.findall(r'{\w+}', self._model.template)
        self.__index       = 0

    def create(self, _):
        "creates the widget"
        self.__columns = re.findall(r'{\w+}', self._model.template)
        text           = self._model.template.format(**dict.fromkeys(self.__columns, 0.))
        self.__widget  = Div(text = text)
        return [self.__widget]

    def observe(self, ctrl):
        """
        add observers to the controller
        """
        ctrl.observe(self._onaddfovlines)

    def _onaddfovlines(self, lines = None, **_):
        new = self.__index + len(lines)
        if new // self._model.refreshrate > self.__index // self._model.refreshrate:
            text = self._model.template.format(**{i: lines[-1][i] for  i in self.__columns})
            self.__widget.update(text = text)
        self.__index = new
