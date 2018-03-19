#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'Deals with undos'
from functools      import wraps, partial
from view           import View

class UndoView(View):
    'View listing all undos'
    def __init__(self, ctrl = None, **kwa): # pylint: disable=too-many-locals
        super().__init__(ctrl = ctrl, **kwa)
        self.__curr = [None]
        ctrl.theme.updatedefaults  ('keystroke',
                                    undo = "Control-z",
                                    redo = "Control-y")
        ctrl.display.updatedefaults('keystroke',
                                    undo = ctrl.undos.undo,
                                    redo = ctrl.undos.redo)
        ctrl.observe('applicationstarted', partial(self.__observe, ctrl))

    def __observe(self, ctrl):
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

        undos = tuple(ctrl.__undos__())
        ctrl.observe([_do(fcn) for fcn in undos if callable(fcn)])
        for und in undos:
            if not callable(und):
                assert sum(1 for i in und if not isinstance(i, str)) == 1
                fcn = next(i for i in und if not isinstance(i, str))
                und = tuple(i for i in und if isinstance(i, str))
                ctrl.observe(*und, _do(fcn))

        # pylint: disable=unused-variable
        @ctrl.observe
        def _onstartaction(recursive = None):
            assert (self.__curr[0] is not None) is recursive
            if not recursive:
                self.__curr[0] = []

        @ctrl.observe
        def _onstopaction(recursive = None, **_):
            assert recursive is not None
            if not recursive:
                self._ctrl.undos.appendundos(self.__curr[0])
                self.__curr[0] = None

        @ctrl.observe
        def _onundoaction(fcn):
            self.__curr[0].append(fcn)
