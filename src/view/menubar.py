#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Menu bar"

from flexx              import ui

from .                  import View
from .dialog            import openfile, savefile

class  MenuBar(ui.Widget, View):
    u"Menu bar"
    def init(self):
        u"initializes gui"
        def _onOpen(*_):
            path = openfile(filetypes = u'trk|*')
            if path is not None:
                self._ctrl.openTrack(path)

        def _onSave(*_):
            fname = savefile(filetypes = u'ana|*')
            if fname is not None:
                raise NotImplementedError("Yet to define an analysis IO")

        with ui.VBox(flex = 0):
            with ui.HBox(flex = 0):
                ui.Button(text = u'open', flex=0).connect('mouse_down', _onOpen)
                ui.Button(text = u'save', flex=0).connect('mouse_down', _onSave)
                ui.Widget(flex = 1)
            ui.Widget(flex = 1)
