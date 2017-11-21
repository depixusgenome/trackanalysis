#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates a tasks property and adds it to the Track
"""
from   typing             import Dict, Any, Union, cast
from   utils.attrdefaults import addattributes
from   data.track         import Track, LazyProperty
from   .tasks             import Tasks, Task

class TaskDescriptor:
    "A descriptor for adding tasks"
    def __init__(self):
        self.name: str = None
        self.__doc__   = ''

    def __get__(self, instance, owner) -> Union[Tasks, Task]:
        if instance is None:
            return Tasks(self.name)
        return instance.tasks.get(self.name, None)

    def __set__(self, instance, value: Union[Dict[str, Any], bool, Task]):
        if not value:
            instance.tasks.pop(self.name)
            return

        if isinstance(value, bool):
            tsk = Tasks(self.name)()
        elif isinstance(value, dict):
            tsk = Tasks(self.name)(**value)
        else:
            try:
                tpe = Tasks(value).value
            except ValueError as exc:
                raise ValueError("Could not create task") from exc
            if tpe != self.name:
                raise ValueError("Could not create task")
            tsk = cast(Task, value)

        instance.tasks[self.name] = tsk

    def __set_name__(self, _, name):
        tsk          = Tasks(name)
        self.name    = tsk.value
        self.__doc__ = tsk.tasktype().__doc__

class LocalTasks:
    """
    Allows setting specific configurations per type of tasks. For
    example:

    ```python
    >>> track.task.alignment = ExtremumAlignmentTask(outlier = .8)
    >>> track.task.alignment = {'outlier': .8} # or using a dictionnary
    ```

    For bead subtraction, it's possible to provides the beads directly:

    ```python
    >>> track.task.subtraction = 1    # subtracting bead 1 from all beads
    >>> track.task.subtraction = 1, 2 # subtracting beads 1 and 2 from all beads
    ```
    """
    def __init__(self) -> None:
        self.tasks: Dict[str, Any] = {}

    def config(self) -> Dict[str, Any]:
        "returns a dictionnary of changes to the current globals"
        cnf      = {'tasks.'+i: j for i, j in self.tasks.items()}
        cleaning = []
        if self.driftpercycle:
            cleaning.append(Tasks.driftpercycle)
        if self.driftperbead:
            cleaning.append(Tasks.driftperbead)

        old      = list(Tasks.__base_cleaning__())
        if len(cleaning):
            cleaning = old[:1] + cleaning + old[1:]
            cnf['tasks.scripting.cleaning.tasks'] = tuple(cleaning)
        return cnf

    cleaning       = TaskDescriptor()
    subtraction    = TaskDescriptor()
    selection      = TaskDescriptor()
    alignment      = TaskDescriptor()
    driftperbead   = TaskDescriptor()
    driftpercycle  = TaskDescriptor()
    eventdetection = TaskDescriptor()
    peakselector   = TaskDescriptor()

Track.tasks = LazyProperty('tasks')
addattributes(Track, protected = dict(tasks = LocalTasks()))

Track.__doc__ += ("""
    * `tasks` a""" + LocalTasks.__doc__[6:])
