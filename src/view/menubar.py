#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Menu bar"

from typing         import Optional     # pylint: disable=unused-import
from flexx          import ui

from control.event  import Controller
from .dialog        import FileDialog
from .              import View

class  MenuBar(ui.Widget, View):
    u"Menu bar"
    _box      = None # type: Optional[ui.HBox]
    _save     = None # type: Optional[ui.Button]
    _open     = None # type: Optional[ui.Button]
    _diagopen = None # type: Optional[FileDialog]
    _diagsave = None # type: Optional[FileDialog]
    def setCtrl(self, ctrl: Controller):
        u"Sets up the controller"
        obs = ctrl is not getattr(self, '_ctrl')

        self._diagopen = FileDialog(filetypes = u'trk|ana|*')
        self._diagsave = FileDialog(filetypes = u'ana|*')
        super().setCtrl(ctrl)
        if not obs:
            return

        def _onUpdateGlobal(**items):
            if self._box is None or 'track' not in items:
                return

            if items['track'].value is not items['empty']:
                self._box.children = self._open, self._save, self._spacer
            else:
                self._box.children = self._open, self._spacer

        ctrl.observe(_onUpdateGlobal)

    def _onOpen(self, *_):
        path = self._diagopen.open()
        if path is not None:
            self._ctrl.openTrack(path)

    def _onSave(self,  *_):
        path = self._diagsave.save()
        if path is not None:
            raise NotImplementedError("Yet to define an analysis IO")

    def init(self):
        u"initializes gui"

        with ui.VBox(flex = 0):
            self._box = ui.HBox(flex = 0)
            with self._box:
                self._open   = ui.Button(text = u'open', flex=0)
                self._save   = ui.Button(text = u'save', flex=0)
                self._spacer = ui.Widget(flex = 1)
            ui.Widget(flex = 1)

        self._open.connect('mouse_down',  self._onOpen)
        self._save.connect('mouse_down',  self._onSave)
        self._box.children = (self._open, self._spacer)
