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
    __isundoing = None # type: bool

    def setCtrl(self, ctrl):
        u"sets up the observations"
        self.__isundoing = False
        self.__uqueue    = deque(maxlen = 1000)
        self.__rqueue    = deque(maxlen = 1000)
        super().setCtrl(ctrl)

        self.__observe(ctrl)
        self.__connect(getattr(self, 'connect', lambda *_: None))

    def __observe(self, ctrl):
        u"sets-up observer methods: depixus event loop"
        # pylint: disable=unused-variable
        def _onOpenTrack(controller = None, model = None, **_):
            task = model[0]
            return lambda: controller.closeTrack(task)

        def _onCloseTrack(controller = None, model = None, **_):
            return lambda: controller.openTrack(model[0], model)

        def _onAddTask(controller = None, parent = None, task = None, **_):
            return lambda: controller.removeTask(parent, task)

        def _onUpdateTask(controller = None, parent = None, task = None,  old = None, **_):
            return lambda: controller.updateTask(parent, task, **old)

        def _onDeleteTask(controller = None, parent = None, task = None,  old = None, **_):
            ind = old.index(task)
            return lambda: controller.addTask(parent, task, ind)

        def _do(fcn):
            @wraps(fcn)
            def _wrap(**kwargs):
                if self.__isundoing:
                    self.__rqueue.append(fcn(**kwargs))
                else:
                    self.__uqueue.append(fcn(**kwargs))
                    self.__rqueue.clear()
            return _wrap

        ctrl.observe([_do(fcn) for name, fcn in locals().items() if name[:3] == '_on'])

    def __connect(self, connect):
        u"sets-up connect methods: flexx event loop"
        def _onKeyPress(*evt):
            if len(evt) > 1:
                return

            cur = '-'.join(evt[0].modifiers)+'-'+evt[0].key
            if   cur == self._ctrl.getConfig("keypress.undo"):
                self.undo()
            elif cur == self._ctrl.getConfig("keypress.redo"):
                self.redo()

        connect("key_press", _onKeyPress)

    def undo(self):
        u"undoes one action"
        if len(self.__uqueue) == 0:
            return

        while self.__isundoing:
            sleep(.01)

        try:
            self.__isundoing = True
            nbu, nbr = len(self.__uqueue), len(self.__rqueue)

            self.__uqueue.pop()()

            assert (nbu-1, nbr+1) == (len(self.__uqueue), len(self.__rqueue))
        finally:
            self.__isundoing = False

    def redo(self):
        u"redoes one action"
        if len(self.__rqueue) == 0:
            return
        self.__rqueue.pop()()
