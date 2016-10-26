#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from collections    import deque
from .              import View

class UndoView(View):
    u"View listing all undos"
    _queue = None # type: deque

    def setCtrl(self, ctrl):
        u"sets up the observations"
        self._queue = deque(maxlen = 1000)
        super().setCtrl(ctrl)

        def _observe(evtname, fcnname, lstfcns = None, dictfcns = None):
            def _fcn(*_, controler = None, **kwargs):
                if lstfcns is None:
                    elems = tuple()
                if all(isinstance(key, str)   for key in lstfcns):
                    elems = tuple(kwargs[key] for key in lstfcns)
                else:
                    elems = lstfcns(**kwargs)

                if dictfcns is None:
                    dico = dict()
                if isinstance(dictfcns, str):
                    dico = kwargs[dictfcns]
                else:
                    dico = dictfcns(**kwargs)

                dico  = dict () if dictfcns is None else dictfcns(**kwargs)
                self._queue.append(lambda: getattr(controler, fcnname)(*elems, **dico))
            self._ctrl.observe(evtname, _fcn)

        _observe('openTrack',  'closeTrack', lambda **kwa: (kwa['model'][0],))
        _observe('closeTrack', 'openTrack',  ('task',   'model'))
        _observe('addTask',    'removeTask', ('parent', 'task'))
        _observe('removeTask', 'addTask',
                 lambda **kwa: (kwa['parent'], kwa['task'], kwa['old'].index(kwa['task'])))
        _observe('updateTask', 'updateTask', ('parent', 'task'), 'old')

    def undo(self):
        u"undoes one action"
        self._queue.pop()()
