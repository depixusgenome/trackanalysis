#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Deals with undos'
from functools      import wraps
from view           import View

class UndoView(View):
    'View listing all undos'
    def __init__(self, ctrl = None, **kwa):
        super().__init__(ctrl = ctrl, **kwa)
        self.__curr = [None]
        ctrl.theme.updatedefaults  ('keystroke',
                                    undo = "Control-z",
                                    redo = "Control-y")
        ctrl.display.updatedefaults('keystroke',
                                    undo = ctrl.undos.undo,
                                    redo = ctrl.undos.redo)

    def __wrapper(self, fcn):
        @wraps(fcn)
        def _wrap(*args, **kwargs):
            if self.__curr[0] is not None:
                val = fcn(*args, **kwargs)
                if val is not None:
                    self.__curr[0].append(val)
        return _wrap

    def observe(self, ctrl):
        'sets up the observations'
        ctrl.__undos__(self.__wrapper)

        @ctrl.display.observe
        def _onstartaction(recursive = None, **_):
            assert (self.__curr[0] is not None) is recursive
            if not recursive:
                self.__curr[0] = []

        @ctrl.display.observe
        def _onstopaction(recursive = None, **_):
            assert recursive is not None
            if not recursive:
                self._ctrl.undos.appendundos(self.__curr[0])
                self.__curr[0] = None

        @ctrl.undos.observe
        def _onundoaction(fcn, **_):
            self.__curr[0].append(fcn)
