#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from functools      import wraps
from view           import View

class UndoException(Exception):
    u"""
    Raised if a GUI action is created without first emitting a 'startaction'.

    On should use the `viewinstance.action` context or
    the `View.action decorator` in every case.
    """
    pass

class UndoView(View):
    u"View listing all undos"
    def __init__(self, **kwa): # pylint: disable=too-many-locals
        super().__init__(**kwa)
        self.__curr = [None, 0]

        self._observe()
        if 'keys' in kwa:
            kwa['keys'].addKeyPress('keypress', undo = self.undo, redo = self.redo)

    def _observe(self):
        u"sets up the observations"
        msg = "User actions must emit 'startaction' and 'stopaction' events"
        def _do(fcn):
            @wraps(fcn)
            def _wrap(**kwargs):
                if self.__curr[0] is None:
                    raise UndoException(msg)

                self.__curr[0].append(fcn(**kwargs))
            return _wrap

        self._ctrl.observe([_do(fcn) for fcn in self._ctrl.__undos__()])
        self.__onstartstop()

    def __onstartstop(self):
        u"Returns the methods for observing user start & stop action delimiters"
        # pylint: disable=unused-variable
        @self._ctrl.observe
        def _onstartaction():
            if self.__curr[0] is None:
                self.__curr[0] = []
                assert self.__curr[1] == 0
            else:
                self.__curr[1] = self.__curr[1]+1 # count nested 'startaction'

        @self._ctrl.observe
        def _onstopaction(**_):
            if self.__curr[1] == 0:
                self._ctrl.appendUndos(self.__curr[0])
                self.__curr[0] = None
            else:
                self.__curr[1] = self.__curr[1]-1 # count nested 'stopaction'

    def close(self):
        u"Removes the controller"
        del self._ctrl

    @View.action
    def undo(self):
        u"undoes one action"
        self._ctrl.undo()

    @View.action
    def redo(self):
        u"redoes one action"
        self._ctrl.undo()
