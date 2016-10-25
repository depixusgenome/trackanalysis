#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Menu bar"

from flexx              import ui

from .                  import View
from .dialog            import openfile, savefile

class  MenuBar(View, ui.Widget):
    u"Menu bar"
    def init(self):
        u"initializes gui"
        with ui.VBox():
            ui.Button(text = 'open').connect('mouse_down', self._doload)
            ui.Button(text = 'save').connect('mouse_down', self._dosave)

    def _doopen(self):
        path = openfile(filetypes = u'trk|*')
        if path is not None:
            self.ctrl.openTrack(path)

    @staticmethod
    def _dosave():
        fname = savefile(filetypes = u'ana|*')
        if fname is not None:
            raise NotImplementedError("Yet to define an analysis IO")
