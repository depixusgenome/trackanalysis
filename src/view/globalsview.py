#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from .              import View

class GlobalsView(View):
    u"View listing all global info"
    def observe(self, ctrl):
        u"sets up the observations"
        super().observe(ctrl)

        ctask  = 'current.task'
        ctrack = 'current.track'

        # pylint: disable=unused-variable
        def _onCloseTrack(model = None, **_):
            isold = ctrl.getGlobal(ctrack) is model[0]
            try:
                tsk = next(next(ctrl.tasktree))
            except StopIteration:
                ctrl.deleteGlobal(ctrack, *((ctask,) if isold else tuple()))
            else:
                ctrl.updateGlobal((ctrack, tsk), *((ctask, tsk),) if isold else tuple())

        def _onOpenTrack(model = None, **_):
            ctrl.updateGlobal(**{ctrack: model[0], ctask : model[0]})

        def _onAddTask(parent = None, task = None, **_):
            ctrl.updateGlobal(**{ctrack: parent, ctask : task})

        def _onUpdateTask(parent = None, task = None, **_):
            ctrl.updateGlobal(**{ctrack: parent, ctask : task})

        def _onDeleteTask(parent = None, **_):
            ctrl.updateGlobal(**{ctrack: parent, ctask : parent})

        ctrl.observe([fcn for name, fcn in locals().items() if name[:3] == '_on'])

    def connect(self, *_1, **_2):
        u"Should be implemetented by flexx.ui.Widget"
        raise NotImplementedError("View should derive from a flexx app")
