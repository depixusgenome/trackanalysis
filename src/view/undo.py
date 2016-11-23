#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from functools      import wraps
from collections    import deque
from .              import View

class UndoException(Exception):
    u"""
    Raised if a GUI action is created without first emitting a 'startaction'.

    On should use the `viewinstance.action` context or
    the `View.action decorator` in every case.
    """
    pass

class UndoView(View):
    u"View listing all undos"
    __uqueue    = None # type: deque
    __rqueue    = None # type: deque
    __isundoing = None # type: List[bool]

    def unobserve(self):
        u"Removes the controller"
        del self.__isundoing
        del self.__uqueue
        del self.__rqueue

    def observe(self, ctrl, keys): # pylint: disable=too-many-locals
        u"sets up the observations"
        keys.addKeyPress('keypress', undo = self.undo, redo = self.redo)

        self.__isundoing = [False]
        self.__uqueue    = deque(maxlen = 1000)
        self.__rqueue    = deque(maxlen = 1000)

        curr = [None, 0]
        def _do(fcn):
            @wraps(fcn)
            def _wrap(**kwargs):
                if curr[0] is None:
                    msg = "User actions must emit 'startaction' and 'stopaction' events"
                    raise UndoException(msg)

                curr[0].append(fcn(**kwargs))
            return _wrap

        isundoing = self.__isundoing
        uqueue    = self.__uqueue
        rqueue    = self.__rqueue

        # pylint: disable=unused-variable
        _1  = None
        def _onOpenTrack(controller = _1, model = _1, **_):
            task = model[0]
            return lambda: controller.closeTrack(task)

        def _onCloseTrack(controller = _1, model = _1, **_):
            return lambda: controller.openTrack(model[0], model)

        def _onAddTask(controller = _1, parent = _1, task = _1, **_):
            return lambda: controller.removeTask(parent, task)

        def _onUpdateTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            return lambda: controller.updateTask(parent, task, **old)

        def _onDeleteTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            ind = old.index(task)
            return lambda: controller.addTask(parent, task, ind)

        ctrl.observe([_do(fcn) for name, fcn in locals().items() if name[:3] == '_on'])

        @ctrl.observe
        def _onstartaction():
            if curr[0] is None:
                curr[0] = []
                assert curr[1] == 0
            else:
                curr[1] = curr[1]+1 # count nested 'startaction'

            if not isundoing[0]:
                rqueue.clear()

        @ctrl.observe
        def _onstopaction(**_):
            items   = curr[0]
            if curr[1] == 0:
                curr[0] = None
            else:
                curr[1] = curr[1]-1 # count nested 'stopaction'

            if len(items) != 0:
                (rqueue if isundoing[0] else uqueue).append(items)

    def _apply(self):
        queue = self.__uqueue if self.__isundoing[0] else self.__rqueue
        if len(queue) == 0:
            return

        items = queue.pop()
        with self.action:
            for fcn in items:
                fcn()

    def undo(self):
        u"undoes one action"
        self.__isundoing[0] = True
        try:
            self._apply()
        finally:
            self.__isundoing[0] = False

    def redo(self):
        u"redoes one action"
        self._apply()
