#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Display the fov data into a table"
import re
from   typing        import Set
from   functools     import partial
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

_TEXT = "".join(_BASE % i for i in (("Cycle",        "cycle"),
                                    ("Magnet µm",    "zmag:.3f"),
                                    ("Objective µm", "zobj:.3f"),
                                    ("X µm",         "x:.3f"),
                                    ("Y µm",         "y:.3f"),
                                    ("Sample °C",    "tsample:.3f"),
                                    ("Box °C",       "tbox:.3f"),
                                    ("Magnet °C",    "tmagnet:.3f")))+"<p></p>"

class FoVTableTheme(BaseModel):
    "summary info on the field of view"
    name        = 'fovtable'
    template    = _TEXT
    period      = 1.
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
        self.__widget:  Div      = None
        self.__direct:  Set[str] = []
        self.__temps:   Set[str] = []
        self.__cycle             = False
        self.__callback          = None

    def _addtodoc(self, ctrl, _):
        "creates the widget"
        names         = set(self._FIND.findall(self._model.template))
        self.__direct = names - {'tsample', 'tbox', 'tmagnet', 'cycle'}
        self.__temps  = names & {'tsample', 'tbox', 'tmagnet'}
        self.__cycle  = 'cycle' in names
        text          = self._model.template.format(**{i: 0. for i in names})

        mods = dict(width  = self._model.width,
                    height = self._model.height)
        self.__widget = Div(text   = text, **mods)

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

        @ctrl.daq.observe
        def _onupdatefov(old = None, **_): # pylint: disable=unused-variable
            if 'fov' in old:
                self.reset(ctrl)

        @ctrl.daq.observe
        def _onlisten(old = None, **_): # pylint: disable=unused-variable
            if 'fovstarted' in old:
                self.reset(ctrl)

    def _reset(self, control, _):
        data                   = control.daq.data
        doadd                  = data.fovstarted
        cback, self.__callback = self.__callback, (True if doadd else None)
        if cback is True:
            return

        if cback is not None:
            self._doc.remove_periodic_callback(cback)

        if self.__callback is True:
            self.__callback = self._doc.add_periodic_callback(partial(self.__data, control),
                                                              self._model.period*1e3)

    def __data(self, ctrl):
        lines = ctrl.daq.data.fov.view()
        if len(lines) == 0:
            return

        out = {i: lines[-1][i] for  i in self.__direct}
        if self.__cycle:
            if lines[-1]['cycle']:
                out['cycle'] = f'{lines[-1]["cycle"]}/{ctrl.daq.config.protocol.cyclecount}'
            else:
                out['cycle'] = '--'

        for i in self.__temps:
            out[i] = ctrl.daq.config.network.fov.temperatures.data(i, lines)[-1]

        self.__widget.text = self._model.template.format(**out)
