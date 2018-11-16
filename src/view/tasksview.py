#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from functools              import partial
from control.beadscontrol   import findanybead
from control.decentralized  import Indirection
from model.task             import Task
from model.task.application import TasksDisplay, TaskIOTheme

class TasksView:
    "View listing all tasks global info"
    _display = Indirection()
    _io      = Indirection()
    def __init__(self, ctrl):
        self._ctrl    = ctrl
        self._display = TasksDisplay()
        self._io      = TaskIOTheme()

    def _onclosetrack(self, ctrl, **_):
        inst = next(ctrl.tasks.tasklist(...), None)
        if inst is not None:
            inst = next(iter(inst), None)
        ctrl.display.update(self._display, roottask = inst)

    def _onopentrack(self, ctrl, model = None, calllater = None, **_):
        calllater.insert(0, partial(self._openedtrack, ctrl,  model[0]))

    def _openedtrack(self, ctrl, root: Task):
        bead = self._display.bead
        if bead is None:
            bead = findanybead(ctrl, root)
        self._display = {'roottask': root, 'bead': bead}

    def observe(self, ctrl):
        "observing the controller"
        ctrl.tasks.observe(closetrack = partial(self._onclosetrack, ctrl),
                           opentrack  = partial(self._onopentrack,  ctrl))
