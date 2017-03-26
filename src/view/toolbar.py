#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Toolbar"
from pathlib              import Path
from bokeh.layouts        import Row

from control.taskio       import TaskIO
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

        self.__diagopen = FileDialog(multiple  = 1,
                                     config    = self._ctrl)
        self.__diagsave = FileDialog(config    = self._ctrl)

    def _getroots(self, _):
        "adds items to doc"
        css         = self._ctrl.getGlobal('css').title
        self._open  = self.button(self._onOpen,  css.open.get())
        self._save  = self.button(self._onSave,  css.save.get(), disabled = True)
        self._tools.extend([self._open, self._save])

        if self._ctrl.ISAPP:
            self._quit = self.button(self._ctrl.close, css.quit.get())
            self._tools.append(self._quit)

        self.__diagopen.filetypes = TaskIO.extensions(self._ctrl, 'openers')
        self.__diagopen.title     = css.open.dialog.get()
        self.__diagsave.filetypes = TaskIO.extensions(self._ctrl, 'savers')
        self.__diagsave.title     = css.save.dialog.get()

    def getroots(self, doc):
        "adds items to doc"
        self._getroots(doc)
        self.enableOnTrack(self._save)
        def _title(item):
            path = getattr(item.value, 'path', None)
            if isinstance(path, (list, tuple)):
                path = path[0]
            title = doc.title.split(':')[0]
            if path is not None and len(path) > 0:
                title += ':' + Path(path).stem
            doc.title = title

        self._ctrl.getGlobal("current").track.observe(_title)
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
        paths = self.__diagopen.open()
        if paths is not None:
            self._ctrl.openTrack(paths)

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
