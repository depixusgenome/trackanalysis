#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Menu bar"

from typing         import Optional     # pylint: disable=unused-import
from flexx          import ui

from .dialog        import FileDialog
from .              import View

class  ToolBar(ui.Widget, View):
    u"Menu bar"
    _box      = None # type: Optional[ui.HBox]
    _save     = None # type: Optional[ui.Button]
    _diagopen = None # type: Optional[FileDialog]
    _diagsave = None # type: Optional[FileDialog]
    def observe(self, ctrl):
        u"Sets up the controller"
        super().observe(ctrl)
        self._diagopen = FileDialog(filetypes = u'trk|ana|*',
                                    config    = ctrl,
                                    title     = u'Open a track or analysis file')
        self._diagsave = FileDialog(filetypes = u'ana|*',
                                    config    = ctrl,
                                    title     = u'Save an analysis file')

        box  = self._box
        save = self._save
        def _onUpdateGlobal(**items):
            if 'current.track' not in items:
                return
            children = list(box.children)
            if items['current.track'].value is not items['empty']:
                children.insert(1, save)
            else:
                children.pop(1)

            box.children = children

        ctrl.observe(_onUpdateGlobal)

    def unobserve(self):
        u"Sets up the controller"
        super().unobserve()
        del self._diagopen
        del self._diagsave

    @View.action
    def _onOpen(self, *_):
        path  = self._diagopen.open()
        if path is not None:
            self._ctrl.openTrack(path)

    @View.action
    def _onSave(self,  *_):
        if self._save not in self._box.children:
            return

        path = self._diagsave.save()
        if path is not None:
            self._ctrl.saveTrack(path)

    def close(self):
        u"closes the application"
        raise NotImplementedError("implemented in src/app/__init__.py")

    def init(self):
        u"initializes gui"
        with ui.VBox(flex = 0):
            self._box = ui.HBox(flex = 0)
            with self._box:
                self.button(self._onOpen, u'open')
                self.button(self._onSave, u'save')
                ui.Widget(flex = 1)
                self.button(lambda *_: self.close(), u'quit')
            ui.Widget(flex = 1)

        children   = list(self._box.children)
        self._save = children.pop(1)
        self._box.children = children
