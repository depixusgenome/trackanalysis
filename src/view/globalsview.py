#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from . import View

class GlobalsView(View):
    u"View listing all global info"
    def __init__(self, **kwa):
        super().__init__(**kwa)

        ctrl = self._ctrl
        cnf  = self._ctrl.getGlobal('current')
        # pylint: disable=unused-variable
        def _onCloseTrack(model = None, **_):
            tasks = ('track',)
            if cnf.track.value is model[0]:
                tasks += ('task',)

            try:
                inst = next(next(ctrl.tasktree))
            except StopIteration:
                del cnf[tasks]
            else:
                cnf.items = {i: inst for i in tasks}

        def _onOpenTrack(model = None, **_):
            cnf.items = {'track': model[0], 'task': model[0]}

        def _onAddTask(parent = None, task = None, **_):
            cnf.items = {'track': parent, 'task' : task}

        def _onUpdateTask(parent = None, task = None, **_):
            cnf.items = {'track': parent, 'task' : task}

        def _onDeleteTask(parent = None, **_):
            cnf.items = {'track': parent, 'task' : parent}

        ctrl.observe([fcn for name, fcn in locals().items() if name[:3] == '_on'])
