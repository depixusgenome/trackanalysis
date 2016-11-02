#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from functools      import wraps
from collections    import deque
from time           import sleep
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

        def _do(fcn):
            isundoing = self.__isundoing
            uqueue    = self.__uqueue
            rqueue    = self.__rqueue
            @wraps(fcn)
            def _wrap(**kwargs):
                if  isundoing[0]:
                    rqueue.append(fcn(**kwargs))
                else:
                    uqueue.append(fcn(**kwargs))
                    rqueue.clear()
            return _wrap

        _1 = None
        # pylint: disable=unused-variable
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

    def connect(self, *_1, **_2):
        u"Should be implemetented by flexx.ui.Widget"
        raise NotImplementedError("View should derive from a flexx app")

    def undo(self):
        u"undoes one action"
        if len(self.__uqueue) == 0:
            return

        while self.__isundoing[0]:
            sleep(.01)

        try:
            self.__isundoing[0] = True
            nbu, nbr = len(self.__uqueue), len(self.__rqueue)

            self.__uqueue.pop()()

            assert (nbu-1, nbr+1) == (len(self.__uqueue), len(self.__rqueue))
        finally:
            self.__isundoing[0] = False

    def redo(self):
        u"redoes one action"
        if len(self.__rqueue) == 0:
            return
        self.__rqueue.pop()()
