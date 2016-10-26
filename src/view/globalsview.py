#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from .              import View

class GlobalsView(View):
    u"View listing all global info"
    def setCtrl(self, ctrl):
        u"sets up the observations"
        super().setCtrl(ctrl)

        # pylint: disable=missing-docstring,unused-variable
        update = self._ctrl.updateGlobal
        delete = self._ctrl.deleteGlobal
        get    = self._ctrl.getGlobal

        def _onTasks():
            def onOpenTrack(model = None, **_):
                update(track = model, task = model)

            def onCloseTrack(old = None, **_):
                isold = get('task') is old
                try:
                    tsk = next(next(self._ctrl.tasktree()))
                except StopIteration:
                    delete('track'+ (('task',) if isold else tuple()))
                else:
                    update(track = tsk, **({'task': tsk} if isold else {}))

            def onDeleteTask(parent = None, **_):
                update(track = parent, task = parent)

            ctrl.observe(locals())

            def onAddTask(parent = None, task = None, **_):
                update(track = parent, task = task)

            ctrl.observe('addTask', 'updateTask', onAddTask)
        _onTasks()
