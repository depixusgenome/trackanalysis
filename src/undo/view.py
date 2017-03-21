#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Deals with undos'
from functools      import wraps
from view           import View

class UndoException(Exception):
    '''
    Raised if a GUI action is created without first emitting a 'startaction'.

    On should use the `viewinstance.action` context or
    the `View.action decorator` in every case.
    '''
    pass

class UndoView(View):
    'View listing all undos'
    def __init__(self, **kwa): # pylint: disable=too-many-locals
        super().__init__(**kwa)
        self.__curr = [None]

        if 'keys' in kwa:
            kwa['keys'].addKeyPress('keypress', undo = self.undo, redo = self.redo)

    def observe(self):
        'sets up the observations'
        msg = "User actions must emit 'startaction' and 'stopaction' events"

        def _do(fcn):
            @wraps(fcn)
            def _wrap(*args, **kwargs):
                if self.__curr[0] is None:
                    raise UndoException(msg)

                self.__curr[0].append(fcn(*args, **kwargs))
            return _wrap

        undos = tuple(self._ctrl.__undos__())
        self._ctrl.observe([_do(fcn) for fcn in undos if callable(fcn)])
        for und in undos:
            if not callable(und):
                self._ctrl.observe(*und)

        self.__onstartstop()

    def __onstartstop(self):
        'Returns the methods for observing user start & stop action delimiters'
        # pylint: disable=unused-variable
        @self._ctrl.observe
        def _onstartaction(recursive = None):
            assert (self.__curr[0] is not None) is recursive
            if not recursive:
                self.__curr[0] = []

        @self._ctrl.observe
        def _onstopaction(recursive = None, **_):
            assert recursive is not None
            if not recursive:
                self._ctrl.appendUndos(self.__curr[0])
                self.__curr[0] = None

    def close(self):
        'Removes the controller'
        del self._ctrl

    @View.action
    def undo(self):
        'undoes one action'
        self._ctrl.undo()

    @View.action
    def redo(self):
        'redoes one action'
        self._ctrl.undo()
