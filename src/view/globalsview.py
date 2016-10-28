#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from .              import View

class GlobalsView(View):
    u"View listing all global info"
    def setCtrl(self, ctrl):
        u"sets up the observations"
        super().setCtrl(ctrl)
        ctrl.observe(self._onOpenTrack, self._onCloseTrack,
                     self._onAddTask,   self._onUpdateTask, self._onDeleteTask)

    def _onCloseTrack(self, old = None, **_):
        isold = self._ctrl.getGlobal('task') is old
        try:
            tsk = next(next(self._ctrl.tasktree()))
        except StopIteration:
            self._ctrl.deleteGlobal('track'+ (('task',) if isold else tuple()))
        else:
            self._ctrl.updateGlobal(track = tsk, **({'task': tsk} if isold else {}))

    def _onOpenTrack(self, model = None, **_):
        self._ctrl.updateGlobal(track = model[0], task = model[0])

    def _onAddTask(self, parent = None, task = None, **_):
        self._ctrl.updateGlobal(track = parent, task = task)

    def _onUpdateTask(self, parent = None, task = None, **_):
        self._ctrl.updateGlobal(track = parent, task = task)

    def _onDeleteTask(self, parent = None, **_):
        self._ctrl.updateGlobal(track = parent, task = parent)
