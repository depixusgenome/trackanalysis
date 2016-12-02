#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with global information"
from . import View

class GlobalsView(View):
    u"View listing all global info"
    def __init__(self, **kwa):
        super().__init__(**kwa)

        ctrl  = self._ctrl
        items = self._ctrl.getGlobal('current')
        # pylint: disable=unused-variable
        def _onCloseTrack(model = None, **_):
            tasks = ('track',)
            if items.track.value is model[0]:
                tasks += ('task',)

            try:
                inst = next(next(ctrl.tasktree))
            except StopIteration:
                del items[tasks]
            else:
                items.values = {i: inst for i in tasks}

        def _onOpenTrack(model = None, **_):
            items.values = {'track': model[0], 'task': model[0]}

        def _onAddTask(parent = None, task = None, **_):
            items.values = {'track': parent, 'task' : task}

        def _onUpdateTask(parent = None, task = None, **_):
            items.values = {'track': parent, 'task' : task}

        def _onDeleteTask(parent = None, **_):
            items.values = {'track': parent, 'task' : parent}

        ctrl.observe([fcn for name, fcn in locals().items() if name[:3] == '_on'])
