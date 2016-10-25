#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Menu bar"

from tkinter            import Tk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from flexx              import ui

from .                  import View
from model.task         import TrackReaderTask

class  MenuBar(View, ui.Widget):
    u"Menu bar"
    def init(self):
        u"initializes gui"
        with ui.VBox():
            ui.Button(text = 'open').connect('mouse_down', self._doload)
            ui.Button(text = 'save').connect('mouse_down', self._dosave)

    def _doopen(self):
        Tk().withdraw()
        fname = askopenfilename(defaultextention = ".trk",
                                filetypes        = [('track files', '.trk'),
                                                    ('all files', '.*')])
        if fname is None:
            return

        self.ctrl.openTrack(TrackReaderTask(path = fname))

    @staticmethod
    def _dosave():
        Tk().withdraw()
        fname = asksaveasfilename(defaultextention = ".ana",
                                  filetypes        = [('analysis files', '.ana'),
                                                      ('all files', '.*')])
        if fname is None:
            return

        raise NotImplementedError("Yet to define an analysis IO")
