#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from functools      import wraps
from collections    import deque
from .              import View

class UndoView(View):
    u"View listing all undos"
    __uqueue    = None # type: deque
    __rqueue    = None # type: deque
    __isundoing = None # type: List[bool]

    def unobserve(self):
        u"Removes the controller"
        super().unobserve()
        del self.__isundoing
        del self.__uqueue
        del self.__rqueue

    def observe(self, ctrl):
        u"sets up the observations"
        super().observe(ctrl)

        self.addKeyPress(undo = self.undo, redo = self.redo)

        self.__isundoing = [False]
        self.__uqueue    = deque(maxlen = 1000)
        self.__rqueue    = deque(maxlen = 1000)

        curr = [None]
        def _do(fcn):
            @wraps(fcn)
            def _wrap(**kwargs):
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
            curr[0] = []
            if not isundoing[0]:
                rqueue.clear()

        @ctrl.observe
        def _onstopaction(**_):
            items   = curr[0]
            curr[0] = None
            if len(items) != 0:
                (rqueue if isundoing[0] else uqueue).append(items)

    def connect(self, *_1, **_2):
        u"Should be implemetented by flexx.ui.Widget"
        raise NotImplementedError("View should derive from a flexx app")

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
