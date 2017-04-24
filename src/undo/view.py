#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Deals with undos'
from functools      import wraps
from view           import View

class UndoView(View):
    'View listing all undos'
    def __init__(self, **kwa): # pylint: disable=too-many-locals
        super().__init__(**kwa)
        self.__curr = [None]
        cnf = self._ctrl.getGlobal('config')
        cnf.keypress.defaults = {'undo'     : "Control-z",
                                 'redo'     : "Control-y"}

        if 'keys' in kwa:
            kwa['keys'].addKeyPress('keypress', undo = self.undo, redo = self.redo)

        self._ctrl.observe('applicationstarted', self.__observe)

    def __observe(self):
        'sets up the observations'
        def _do(fcn):
            @wraps(fcn)
            def _wrap(*args, **kwargs):
                if self.__curr[0] is None:
                    return # could be a bug or just bokeh-startup

                val = fcn(*args, **kwargs)
                if val is None:
                    return

                self.__curr[0].append(val)
            return _wrap

        undos = tuple(self._ctrl.__undos__())
        self._ctrl.observe([_do(fcn) for fcn in undos if callable(fcn)])
        for und in undos:
            if not callable(und):
                assert sum(1 for i in und if not isinstance(i, str)) == 1
                fcn = next(i for i in und if not isinstance(i, str))
                und = tuple(i for i in und if isinstance(i, str))
                self._ctrl.observe(*und, _do(fcn))

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

        @self._ctrl.observe
        def _onundoaction(fcn):
            self.__curr[0].append(fcn)

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
        self._ctrl.redo()
