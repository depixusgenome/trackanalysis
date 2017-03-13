#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
from bokeh.layouts        import Row

from .dialog              import FileDialog
from .intinput            import BeadInput
from .                    import BokehView

class  ToolBar(BokehView):
    "Toolbar"
    def __init__(self, **kwa):
        "Sets up the controller"
        super().__init__(**kwa)
        self._open  = self.button(self._onOpen,  u'open')
        self._save  = self.button(self._onSave,  u'save', disabled = True)
        self._tools = [self._open, self._save]

        if self._ctrl.ISAPP:
            self._quit = self.button(self._ctrl.close, u'quit')
            self._tools.append(self._quit)

        cnf               = self._ctrl.getGlobal("config").last.path
        cnf.defaults      = dict.fromkeys(FileDialog.DEFAULTS, None)
        cnf.fasta.default = "../tests/testingcore/hairpins.fasta"

        self.__diagopen = FileDialog(filetypes = 'trk|ana|*',
                                     config    = self._ctrl,
                                     title     = u'Open a track or analysis file')
        self.__diagsave = FileDialog(filetypes = 'ana|*',
                                     config    = self._ctrl,
                                     title     = u'Save an analysis file')

        self._ctrl.observe("globals.current", self._onUpdateCurrent)

    def getroots(self):
        "adds items to doc"
        return Row(children = self._tools, sizing_mode = 'fixed'),

    def close(self):
        "Sets up the controller"
        super().close()
        del self._tools
        del self._open
        del self._save
        del self._quit
        del self.__diagopen
        del self.__diagsave

    def _onUpdateCurrent(self, items:dict):
        if 'track' in items:
            self._save.disabled = items['track'].value is items['empty']

    @BokehView.action
    def _onOpen(self, *_):
        path  = self.__diagopen.open()
        if path is not None:
            self._ctrl.openTrack(path)

    @BokehView.action
    def _onSave(self,  *_):
        if self._save.disabled:
            return

        path = self.__diagsave.save()
        if path is not None:
            self._ctrl.saveTrack(path)

class  BeadToolBar(ToolBar):
    "Toolbar with a bead spinner"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self._beads = BeadInput(**kwa)
        self._beads.addkeypress()
        self._tools.insert(2, self._beads.input)

    def close(self):
        "Sets up the controller"
        super().close()
        self._beads.close()
        del self._beads
