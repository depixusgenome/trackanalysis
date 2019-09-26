#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from functools                import partial
from itertools                import chain
from taskcontrol.beadscontrol import BeadController
from taskmodel.application    import TasksDisplay, TaskIOTheme

class TasksView:
    "View listing all tasks global info"
    def __init__(self, ctrl):
        self._display = TasksDisplay()
        self._io      = TaskIOTheme()
        if ctrl:
            self._display = ctrl.display.add(TasksDisplay(), False)
            self._io      = ctrl.theme.add(TaskIOTheme(), False)

    def _ontask(self, ctrl, calllater, **_):
        calllater.insert(0, partial(self._openedtrack, ctrl, self._display.taskcache))

    def _onclosetrack(self, ctrl, new, calllater, **_):
        calllater.insert(0, partial(self._openedtrack, ctrl, new))

    def _onopentrack(self, ctrl, taskcache, calllater, **_):
        calllater.insert(0, partial(self._openedtrack, ctrl, taskcache))

    def _openedtrack(self, ctrl, taskcache):
        old       = self._display.bead
        beadsctrl = BeadController(taskcache = taskcache, bead = old)
        if beadsctrl.track is None:
            bead  = None
        else:
            selected  = sorted(beadsctrl.availablebeads)
            bead      = (
                None                        if not selected    else
                old                         if old in selected else
                next(iter(selected), None)  if old is None     else
                next(
                    chain(
                        (i for i in selected if i > old),
                        (i for i in selected if i < old)
                    ),
                    None
                )
            )

        args = {}

        if taskcache is not self._display.taskcache:
            args['taskcache'] = taskcache
        if bead != old:
            args['bead'] = bead

        if args:
            ctrl.display.update(self._display, **args)

    def observe(self, ctrl):
        "observing the controller"
        ctrl.tasks.observe(
            closetrack = partial(self._onclosetrack, ctrl),
            opentrack  = partial(self._onopentrack,  ctrl),
            updatetask = partial(self._ontask,       ctrl),
            addtask    = partial(self._ontask,       ctrl),
            removetask = partial(self._ontask,       ctrl)
        )
