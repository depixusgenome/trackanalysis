#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with bead selection"
from typing                     import Optional, Iterator, Iterable, cast

from control.decentralized      import Indirection
from data.track                 import Track
from model.task                 import RootTask, DataSelectionTask
from model.task.application     import TasksDisplay

def getavailablebeads(ctrl, root) -> Iterable[int]:
    "return available beads"
    track = ctrl.tasks.track(root)
    if track is None:
        return iter(tuple())

    procs    = ctrl.tasks.processors(root)
    if procs is None:
        return iter(tuple())

    selected = None
    for itm in procs.data.items():
        selected = itm.proc.beads(itm.cache(), selected)
    return cast(Iterable[int], selected)

def findanybead(ctrl, root) -> Optional[int]:
    "find a starting bead"
    return next(iter(getavailablebeads(ctrl, root)), None)

class BeadController:
    "Deals with bead selection"
    _tasksdisplay = Indirection()
    def __init__(self, ctrl) -> None:
        self._ctrl         = ctrl
        self._tasksdisplay = TasksDisplay()

    @property
    def roottask(self) -> Optional[RootTask]:
        "returns the current root task"
        return self._tasksdisplay.roottask

    @property
    def track(self) -> Optional[Track]:
        "returns the current root task"
        return self._tasksdisplay.track(self._ctrl)

    @property
    def allbeads(self) -> Iterator[int]:
        "returns all beads"
        track = self.track
        return iter(()) if track is None else cast(Iterator[int], track.beads.keys())

    @property
    def availablebeads(self) -> Iterable[int]:
        "returns available beads"
        return getavailablebeads(self._ctrl, self._tasksdisplay.roottask)

    @property
    def discarded(self):
        "returns discarded beads"
        sel = frozenset(self.availablebeads)
        return (i for i in self.allbeads if i not in sel)

    @property
    def bead(self) -> Optional[int]:
        "returns the current bead number"
        bead = self._tasksdisplay.bead
        if bead is None:
            return findanybead(self._ctrl, self._tasksdisplay.roottask)
        return bead

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
        bead = self._tasksdisplay.bead
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
        return (cast(Iterable[int], tuple()) if tsk is None else
                cast(Iterable[int], tsk.discarded))

    @discarded.setter
    def discarded(self, vals: Iterable[int]):
        "sets beads discarded by the DataSelectionTask"
        root = self.roottask
        if root is None:
            return
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

class TaskWidgetEnabler:
    "suger for enabling a list of widgets"
    def __init__(self, *args, track = True, bead = False):
        self.items: list = []
        self.track       = track
        self.bead        = bead
        self.extend(*args)

    def extend(self, *aitms):
        "extends the list of items"
        def _get(obj, litms):
            if isinstance(obj, (tuple, list)):
                for i in obj:
                    _get(i, litms)
            elif isinstance(obj, dict):
                for i in obj.values():
                    _get(i, litms)
            else:
                litms.append((obj, 'frozen' if hasattr(obj, 'frozen') else 'disabled'))
            return litms

        itms = tuple(_get(aitms, []))
        for ite, attr in itms:
            setattr(ite, attr, True)
        self.items.extend(itms)

    def observe(self, ctrl):
        "observe a list of items"
        ctrl.display.observe(self._ontasks)

    def disable(self, cache, val):
        "disables items"
        for ite, attr in self.items:
            cache[ite].update({attr: val})

    def _ontasks(self, old = None, model = None, **_):
        if (self.track and 'roottask' in old) or (self.bead and 'bead' in old):
            val = model.roottask is None
            for ite, attr in self.items:
                setattr(ite, attr, val)

def enablewidgets(ctrl, *aitems, track = True, bead = False) -> TaskWidgetEnabler:
    "enables/disables items as a function of tasks & tracks"
    out = TaskWidgetEnabler(track = track, bead = bead)
    out.extend(*aitems)
    if ctrl:
        out.observe(ctrl)
    return out
