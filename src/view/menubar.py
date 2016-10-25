#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Menu bar"

from flexx              import ui

from model.task         import TrackReaderTask
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
        openfile(filetypes = u'trk|all',
                 fcn       = lambda path: self.ctrl.openTrack(path))

    @staticmethod
    def _dosave():
        fname = savefile(filetypes = u'ana|all')
        if fname is not None:
            raise NotImplementedError("Yet to define an analysis IO")
