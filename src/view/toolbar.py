#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Toolbar"
from bokeh.layouts        import Row

from .dialog              import FileDialog
from .                    import BokehView

class  ToolBar(BokehView):
    u"Toolbar"
    def __init__(self, **kwa):
        u"Sets up the controller"
        super().__init__(**kwa)
        self._tools    = [self.button(self._onOpen,  u'open'),
                          self.button(self._onSave,  u'save', disabled = True)]
        if self._ctrl.ISAPP:
            self._tools.append(self.button(self._ctrl.close, u'quit'))

        self._diagopen = FileDialog(filetypes = u'trk|ana|*',
                                    config    = self._ctrl,
                                    title     = u'Open a track or analysis file')
        self._diagsave = FileDialog(filetypes = u'ana|*',
                                    config    = self._ctrl,
                                    title     = u'Save an analysis file')

        self._ctrl.observe("globals.current", self._onUpdateCurrent)

    def getroots(self):
        u"adds items to doc"
        return Row(children = self._tools, sizing_mode = 'fixed'),

    def close(self):
        u"Sets up the controller"
        super().close()
        del self._tools
        del self._diagopen
        del self._diagsave

    def _onUpdateCurrent(self, **items):
        if 'track' not in items:
            return
        self._tools[1].disabled = items['track'].value is items['empty']

    @BokehView.action
    def _onOpen(self, *_):
        path  = self._diagopen.open()
        if path is not None:
            self._ctrl.openTrack(path)

    @BokehView.action
    def _onSave(self,  *_):
        if self._tools[1].disabled:
            return

        path = self._diagsave.save()
        if path is not None:
            self._ctrl.saveTrack(path)
