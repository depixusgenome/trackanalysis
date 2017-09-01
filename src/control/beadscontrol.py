#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with bead selection"
from typing             import Optional, Iterator
from model.task         import RootTask, DataSelectionTask

class BeadController:
    "Deals with bead selection"
    def __init__(self, ctrl):
        self._ctrl = ctrl

    @property
    def project(self):
        "returns globals for the project"
        return self._ctrl.getGlobal("project")

    @property
    def availablebeads(self) -> Iterator[int]:
        "returns available beads"
        if self.roottask is None:
            return iter(())

        frame = next(self._ctrl.run(self.roottask, DataSelectionTask))
        return frame.withbeadsonly().keys()

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current root task"
        return self.project.track.get()

    @property
    def bead(self) -> Optional[int]:
        "returns the current bead number"
        bead = self.project.bead.get()
        return next(iter(self.availablebeads), None) if bead is None else bead

    @bead.setter
    def bead(self, value) -> Optional[int]:
        """
        Sets the current bead as follows:
           * *value is None*: the new current bead is the one after the current if any,
           * *value is not None*: the new current bead is either *value* or the first
           available bead after *value*.
        """
        bead = self.project.bead.get()
        if value == bead:
            return bead

        if value is None and bead is None:
            value = next(self.availablebeads, None)

        else:
            available = self.availablebeads
            first     = next(available, None)
            if first is None or (value is not None and value <= first):
                value = first
            elif value is None:
                value = next((i for i in available if i > bead), first)
            else:
                value = next((i for i in available if i >= value), first)

        print("new bead", value)
        self.project.bead.set(value)
        return value

    @property
    def discarded(self):
        "returns discarded beads"
        allb = set(self._ctrl.track(self.roottask).beadsonly.keys())
        good = set(self.availablebeads)
        print("disc", allb, good, allb-good)
        return allb-good

    @discarded.setter
    def discarded(self, vals):
        "returns discarded beads"
        vals = set(vals)
        if vals == self.discarded:
            return

        root = self.roottask
        task = self._ctrl.task(root, DataSelectionTask)
        if task is None:
            self._ctrl.addTask(root, DataSelectionTask(discarded = list(vals)), index = 1)
        elif len(vals) == 0:
            self._ctrl.removeTask(root, task)
        else:
            self._ctrl.updateTask(root, task, discarded = list(vals))
