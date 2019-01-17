#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Deals with undos"
from collections    import deque

class UndoModel:
    u"Model listing all undos"
    undos: deque
    redos: deque
    def __init__(self, **kwa):
        maxlen     = kwa.get('maxlen', 1000)
        self.undos = kwa.get('undos', deque(maxlen = maxlen))
        self.redos = kwa.get('redos', deque(maxlen = maxlen))

    def clear(self):
        u"Clears the instance"
        self.undos.clear()
        self.redos.clear()

    def pop(self, isundoing):
        u"Pops a list of undos"
        queue = self.undos if isundoing else self.redos
        return tuple() if len(queue) == 0 else queue.pop()

    def append(self, isundoing, items):
        u"Appends to a list of undos"
        if not isundoing:
            self.redos.clear()

        assert len(items)
        (self.redos if isundoing else self.undos).append(items)
