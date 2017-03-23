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
        self._open  = None
        self._save  = None
        self._quit  = None
        self._tools = []

        css          = self._ctrl.getGlobal('css').title
        css.defaults = {'open': u'Open', 'save': u'Save', 'quit': u'Quit',
                        'open.dialog': u'Open a track or analysis file',
                        'save.dialog': u'Save an analysis file'}

        self.__diagopen = FileDialog(filetypes = 'trk|ana|*',
                                     config    = self._ctrl)
        self.__diagsave = FileDialog(filetypes = 'ana|*',
                                     config    = self._ctrl)

    def _getroots(self, _):
        "adds items to doc"
        css         = self._ctrl.getGlobal('css').title
        self._open  = self.button(self._onOpen,  css.open.get())
        self._save  = self.button(self._onSave,  css.save.get(), disabled = True)
        self._tools.extend([self._open, self._save])

        if self._ctrl.ISAPP:
            self._quit = self.button(self._ctrl.close, css.quit.get())
            self._tools.append(self._quit)

        self.__diagopen.title = css.open.dialog.get()
        self.__diagsave.title = css.save.dialog.get()

    def getroots(self, doc):
        "adds items to doc"
        self._getroots(doc)
        self.enableOnTrack(self._save)
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

    def _getroots(self, doc):
        super()._getroots(doc)
        self._beads.observe(doc)
        self._tools.insert(2, self._beads.input)

    def close(self):
        "Sets up the controller"
        super().close()
        self._beads.close()
        del self._beads
