#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from collections    import deque
from .              import View

class UndoView(View):
    u"View listing all undos"
    def __init__(self, **kwargs):
        self._queue = deque(maxlen = kwargs.get('maxlen', 1000))

    def init(self):
        u"sets up the observations"
        def _observe(evtname, fcnname, *args):
            def _fcn(*_, lst = args, controler = None, **kwargs):
                elems = tuple(kwargs[name] for name in lst if name[0] != '*')
                elems+= next (kwargs[name] for name in lst if name[0] == '*' and name[1] != '*')
                dico  = next (kwargs[name] for name in lst if name[:2] == '**')
                self._queue.append(lambda: getattr(controler, fcnname)(*elems, **dico))
            self._ctrl.observe(evtname, _fcn)

        _observe('openTrack',  'closeTrack', 'task')
        _observe('closeTrack', 'openTrack',  'task', 'model')
        _observe('addTask',    'removeTask', 'parent', 'task')
        _observe('updateTask', 'updateTask', 'parent', 'task', '**old')

        def onRemoveTask(*_, controler = None, parent = None, task = None, old = None):
            u"reverses TaskControler.addTrack"
            ind = old.index(task)
            self._queue.append(lambda: controler.addTask(parent, task, ind))
        self._ctrl.observe(onRemoveTask)

    def undo(self):
        u"undoes one action"
        self._queue.pop()()
