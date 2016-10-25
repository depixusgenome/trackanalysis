#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from utils          import isfunction
from .              import View

class GlobalsView(View):
    u"View listing all global info"
    def init(self):
        u"sets up the observations"
        # pylint: disable=missing-docstring,unused-variable
        update = self._ctrl.updateGlobal
        delete = self._ctrl.deleteGlobal
        get    = self._ctrl.getGlobal

        def _apply(fcn):
            for name, fcn in fcn().items():
                if isfunction(fcn) and name.startswith('on'):
                    self._ctrl.observe(fcn)

        @_apply
        def _onTasks():
            def onOpenTrack(**kwargs):
                update(track = kwargs['task'], task = kwargs['task'])

            def onCloseTrack(**kwargs):
                isold = get('task') is kwargs['old']
                try:
                    tsk = next(next(self._ctrl.tasktree()))
                except StopIteration:
                    delete('track'+ (('task',) if isold else tuple()))
                else:
                    update(track = tsk, **({'task': tsk} if isold else {}))

            def onAddTask(**kwargs):
                update(track = kwargs['parent'], task = kwargs['task'])

            def onUpdateTask(**kwargs):
                update(track = kwargs['parent'], task = kwargs['task'])

            def onDeleteTask(**kwargs):
                update(track = kwargs['parent'], task = kwargs['parent'])

            return locals()
