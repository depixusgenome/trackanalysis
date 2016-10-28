#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from typing         import NamedTuple, Callable
from collections    import deque
from time           import sleep
from .              import View

UndoAction = NamedTuple('UndoAction', [('name', str), ('undo', Callable[[], None])])

class UndoView(View):
    u"View listing all undos"
    _uqueue    = None # type: deque
    _rqueue    = None # type: deque
    _isundoing = None # type: bool

    def setCtrl(self, ctrl):
        u"sets up the observations"
        self._isundoing = False
        self._uqueue    = deque(maxlen = 1000)
        self._rqueue    = deque(maxlen = 1000)
        super().setCtrl(ctrl)

        ctrl.observe(self._onOpenTrack, self._onCloseTrack,
                     self._onAddTask,   self._onUpdateTask, self._onDeleteTask)

    def _append(self, fcn):
        if self._isundoing:
            self._rqueue.append(fcn)
        else:
            self._uqueue.append(fcn)
            self._rqueue.clear()

    def _onOpenTrack(self, controller = None, model = None, **_):
        task = model[0]
        self._append(lambda: controller.closeTrack(task))

    def _onCloseTrack(self, controller = None, model = None, **_):
        self._append(lambda: controller.openTrack(model[0], model))

    def _onAddTask(self, controller = None, parent = None, task = None, **_):
        self._append(lambda: controller.removeTask(parent, task))

    def _onUpdateTask(self, controller = None, parent = None, task = None,  old = None, **_):
        self._append(lambda: controller.updateTask(parent, task, **old))

    def _onDeleteTask(self, controller = None, parent = None, task = None,  old = None, **_):
        ind = old.index(task)
        self._append(lambda: controller.addTask(parent, task, ind))

    def undo(self):
        u"undoes one action"
        while self._isundoing:
            sleep(.01)

        try:
            self._isundoing = True
            nbu, nbr = len(self._uqueue), len(self._rqueue)

            self._uqueue.pop()[-1]()

            assert (nbu-1, nbr+1) == (len(self._uqueue), len(self._rqueue))
        finally:
            self._isundoing = False

    def redo(self):
        u"redoes one action"
        self._rqueue.pop()[-1]()
