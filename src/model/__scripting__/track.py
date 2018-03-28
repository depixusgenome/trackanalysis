#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creates a tasks property and adds it to the Track
"""
from   copy               import copy as shallowcopy
from   typing             import Dict, Any, Union, Optional, cast
from   pathlib            import Path

import anastore
from   utils.attrdefaults import addattributes
from   data.track         import Track, LazyProperty
from   .tasks             import Tasks, Task

class TaskDescriptor:
    "A descriptor for adding tasks"
    def __init__(self):
        self.name: str = None
        self.__doc__   = ''

    def __get__(self, instance, owner) -> Union['TaskDescriptor', Optional[Task]]:
        return self if instance is None else instance.tasks.get(self.name, None)

    def __delete__(self, instance):
        instance.tasks.pop(self.name, None)

    def __set__(self, instance, value: Union[Dict[str, Any], bool, Task]):
        if not value:
            instance.tasks.pop(self.name, None)
            return

        if isinstance(value, bool):
            tsk = Tasks(self.name)()
        elif isinstance(value, dict):
            tsk = Tasks(self.name)(**value)
        else:
            try:
                tpe = Tasks(value).name
            except ValueError as exc:
                raise ValueError("Could not create task") from exc
            if tpe != self.name:
                raise ValueError("Could not create task")
            tsk = cast(Task, value)

        instance.tasks[self.name] = tsk

    def __set_name__(self, _, name):
        tsk          = Tasks(name)
        self.name    = tsk.name
        self.__doc__ = tsk.tasktype().__doc__

class LocalTasks:
    """
    Allows setting specific configurations per type of tasks. For
    example:

    ```python
    >>> track.tasks.alignment    = ExtremumAlignmentTask(outlier = .8)
    >>> track.tasks.alignment    = {'outlier': .8} # or using a dictionnary
    >>> track.tasks.driftperbead = True            # activate with default settings
    ```

    For bead subtraction, it's possible to provides the beads directly:

    ```python
    >>> track.tasks.subtraction = 1    # subtracting bead 1 from all beads
    >>> track.tasks.subtraction = 1, 2 # subtracting beads 1 and 2 from all beads
    ```
    """
    def __init__(self) -> None:
        self.tasks: Dict[str, Any] = {}

    def __eq__(self, obj):
        if obj.__class__ is not self.__class__:
            return False
        if set(obj.tasks) != set(self.tasks):
            return False
        return all(j == obj.tasks[i] for i, j in self.tasks.items())

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

    def load(self, path: Union[str, Path, list]):
        """
        loads local tasks from file path
        """
        mdl    = (path if isinstance(path, list) else
                  anastore.load(str(path))['tasks'][0])
        for i in mdl:
            if hasattr(self, Tasks(i).name) and Tasks(i)() != i:
                setattr(self, Tasks(i).name, i)

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

def localtasks(self: Track, *args, force = True, **kwa) -> Track:
    """
    Creates a copy of the current track, defining the local tasks specifically.

    ```python
    >>> track = Track(path = "...")
    >>> assert track.localtasks(subtraction = 1).tasks.subtraction.beads == [1]
    >>> assert track.subtraction.beads is None
    ```
    """
    cpy = shallowcopy(self)
    for i in args:
        if force or (isinstance(i, Task) and i != Tasks(i)()):
            setattr(cpy.tasks, Tasks(i).name, i) # type: ignore

    for i, j in kwa.items():
        setattr(cpy.tasks, i, j) # type: ignore
    return cpy
Track.localtasks = localtasks

Track.__doc__ += ("""
    * `tasks` a""" + LocalTasks.__doc__[6:])
