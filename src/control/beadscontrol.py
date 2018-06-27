#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with bead selection"
from typing                     import Optional, Iterator, Iterable, cast
from model.task                 import RootTask, DataSelectionTask
from model.task.application     import TasksDisplay
from data.track                 import Track

class BeadController:
    "Deals with bead selection"
    def __init__(self, ctrl, mdl: TasksDisplay = None) -> None:
        self._ctrl   = ctrl
        self.__tasks = cast(TasksDisplay, mdl if mdl else self._ctrl.display.model("tasks"))

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current root task"
        return self.__tasks.roottask

    @property
    def track(self) -> Optional[Track]:
        "returns the current root task"
        return self.__tasks.track(self._ctrl)

    @property
    def allbeads(self) -> Iterator[int]:
        "returns all beads"
        track = self.track
        return iter(()) if track is None else cast(Iterator[int], track.beads.keys())

    @property
    def availablebeads(self) -> Iterable[int]:
        "returns available beads"
        if self.track is None:
            return iter(tuple())

        selected = None
        procs    = self.__tasks.processors(self._ctrl)
        if procs is None:
            return iter(tuple())

        for itm in procs.data.items():
            selected = itm.proc.beads(itm.cache(), selected)
        return selected

    @property
    def discarded(self):
        "returns discarded beads"
        sel = frozenset(self.availablebeads)
        return (i for i in self.allbeads if i not in sel)

    @property
    def bead(self) -> Optional[int]:
        "returns the current bead number"
        bead = self.__tasks.bead
        return next(iter(self.availablebeads), None) if bead is None else bead

    @bead.setter
    def bead(self, value):
        """
        Sets the current bead as follows:
           * *value is None*: the new current bead is the one after the current if any,
           * *value < current*: the new current bead is either *value* or the first
           available bead prior to *value*.
           * *value > current*: the new current bead is either *value* or the first
           available bead beyond *value*.
        """
        bead = self.__tasks.bead
        if value == bead:
            return

        if value is None:
            if bead is None:
                value = next(iter(self.availablebeads), bead)
            else:
                value = next(iter(i for i in self.availablebeads if i > bead), bead)

        elif bead is None or value > bead:
            value = next(iter(i for i in self.availablebeads if i >= value), bead)
        else:
            last  = None
            for i in self.availablebeads:
                if i > value:
                    break
                last = i

            value = bead if last is None else last

        if value != bead:
            self._ctrl.display.update("tasks", bead = value)

class DataSelectionBeadController(BeadController):
    "controller for discarding beads using a DataSelectionTask"
    @property
    def task(self) -> Optional[DataSelectionTask]:
        "returns the current DataSelectionTask"
        return self._ctrl.tasks.task(self.roottask, DataSelectionTask)

    @property
    def discarded(self) -> Iterable[int]:
        "returns beads discarded by the DataSelectionTask"
        tsk = self.task
        return cast(Iterable[int], tuple()) if tsk is None else tsk.discarded

    @discarded.setter
    def discarded(self, vals: Iterable[int]):
        "sets beads discarded by the DataSelectionTask"
        root = self.roottask
        tsk  = self.task
        vals = frozenset(vals)
        if (root is None
                or not (vals or tsk)
                or (vals == getattr(tsk, 'discarded', frozenset()))):
            return

        if tsk is None:
            tsk = DataSelectionTask(discarded = list(vals))
            self._ctrl.tasks.addtask(root, tsk, index = 'auto')

        elif len(vals) == 0:
            self._ctrl.tasks.removetask(root, tsk)
        else:
            self._ctrl.tasks.updatetask(root, tsk, discarded = list(vals))
