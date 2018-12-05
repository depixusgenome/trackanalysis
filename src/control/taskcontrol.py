#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task controller.

The controller stores:
    - lists of tasks (ProcessorController.model),
    - their associated processors and cache (ProcessorController.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing          import (Union, Iterator, Type, cast, Tuple,
                             Optional, Any, List, Iterable, Dict, overload,
                             TYPE_CHECKING)
from pathlib         import Path
from functools       import partial

from model.task      import Task, RootTask, TaskIsUniqueError
from .event          import Controller, NoEmission
from .processor      import Cache, Processor, run as _runprocessors
from .processor.base import register, ProcCache
from .taskio         import openmodels

if TYPE_CHECKING:
    from data import Track # pylint: disable=unused-import
    class _Ellipsis:
        pass

_none      = type('_none', (), {})
_Proc      = Type[Processor]
_Procs     = Union[Iterable[_Proc], _Proc]
PATHTYPE   = Union[str, Path]
PATHTYPES  = Union[PATHTYPE,Tuple[PATHTYPE,...]]

class ProcessorController:
    "data and model for tasks"
    __slots__ = ('model', 'data', 'copy')
    def __init__(self, copy = False):
        self.model: List[Task] = []
        self.data              = Cache()
        self.copy              = copy

    def task(self, task:Union[Type[Task],int], noemission = False) -> Optional[Task]:
        "returns a task"
        tsk = None
        if isinstance(task, Task):
            tsk = task

        elif isinstance(task, int):
            tsk = self.model[task]

        elif isinstance(task, type):
            try:
                tsk = next(i for i in self.model if isinstance(i, task))
            except StopIteration:
                pass

        if tsk is None and noemission:
            raise NoEmission("Missing task")
        return tsk

    def add(self, task, proctype, index = _none):
        "adds a task to the list"
        TaskIsUniqueError.verify(task, self.model)
        proc = proctype(task)

        if index is _none:
            self.model.append(task)
            self.data .append(proc)
        else:
            self.model.insert(index, task)
            self.data .insert(index, proc)

    def remove(self, task):
        "removes a task from the list"
        task = self.task(task)

        self.model.remove(task)
        self.data .remove(task)

    def update(self, tsk):
        "clears data starting at *tsk*"
        self.data.delCache(tsk)

    def cleancopy(self) -> 'ProcessorController':
        "returns a cache with only the processors"
        cpy = self.__class__(copy = self.copy)
        cpy.model = self.model
        cpy.data  = self.data.cleancopy()
        return cpy

    def clear(self):
        "clears data starting at *tsk*"
        self.data.delCache()

    def run(self, tsk:Task = None, copy = None, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return _runprocessors(self.data, tsk,
                              copy = self.copy if copy is None else copy,
                              pool = pool)

    def keepupto(self, tsk:Task = None, included = True) -> 'ProcessorController':
        "Returns a processor for a given root and range"
        ind         = None if tsk is None else self.data.index(tsk)
        other       = type(self)(copy = self.copy)
        other.model = self.model[:None if ind is None else ind+(1 if included else 0)]
        other.data  = self.data.keepupto(ind, included)
        return other

    @classmethod
    def create(cls, *models : Task, processors: Union[Dict,_Procs,None] = Processor
              ) -> 'ProcessorController':
        "creates a task pair for this model"
        tasks = [] # type: List[Task]
        for i in models:
            if isinstance(i, Task):
                tasks.append(i)
            else:
                tasks.extend(cast(Iterable[Task], i))

        if len(tasks) == 0:
            raise IndexError('no models were provided')

        if not isinstance(tasks[0], RootTask):
            raise TypeError(f'Argument #0 ({tasks[0]}) should  be a RootTask')

        if not all(isinstance(i, Task) for i in tasks):
            ind, wrong = next((i, j) for i, j in enumerate(tasks) if not isinstance(j, Task))
            raise TypeError(f'Argument #{ind} ({wrong}) should  be a Task')

        pair  = cls()
        if not isinstance(processors, Dict):
            processors = cls.register(processors)

        for other in tasks:
            pair.add(other, processors[type(other)])
        return pair

    @classmethod
    def register(cls,
                 processor: _Procs     = None,
                 cache:     ProcCache  = None,
                 force                 = False,
                ) -> Dict[Type[Task], Type[Processor]]:
        "registers a task processor"
        return register(processor, force, cache, True)

create   = ProcessorController.create # pylint: disable=invalid-name

class BaseTaskController(Controller):
    "Data controller class"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items: Dict[RootTask, ProcessorController] = dict()
        self._procs: Dict[Type[Task], Type[Processor]]   = dict()
        self._procs   = (register(kwargs['processors'])
                         if 'processors' in kwargs else None)

        self._openers = kwargs.get("openers", None)
        self._savers  = kwargs.get("savers",  None)

    def __repr__(self):
        return "TaskControl"

    @property
    def tasks(self):
        "return self"
        return self

    @property
    def __processors(self):
        if self._procs is None:
            self._procs = register(Processor)
        return self._procs

    def task(self,
             parent : Optional[RootTask],
             task   : Union[Type[Task], int],
             noemission = False) -> Optional[Task]:
        "returns a task"
        ctrl = self._items[parent] if parent in self._items else ProcessorController()
        return ctrl.task(task, noemission = noemission)

    # pylint: disable=no-self-use,unused-argument,function-redefined
    @overload
    def track(self, parent: None) -> None:
        "returns None"

    @overload
    def track(self, parent: RootTask) -> 'Track':
        "returns the root cache, i;e. the track"

    @overload
    def track(self, parent: '_Ellipsis') -> Iterator['Track']: # type: ignore
        "returns all root cache, i;e. tracks"

    def track(self, parent):
        "returns the root cache, i;e. the track"
        if parent is Ellipsis:
            return (i.data[0].cache() for i in self._items.values())

        if parent not in self._items:
            return None

        track = self._items[parent].data[0].cache()
        if track is None:
            self._items[parent].run(parent) # create cache if needed
            track = self._items[parent].data[0].cache()
        return track

    def tasklist(self, parent: Union[None, '_Ellipsis', RootTask]
                ) -> Union[Iterator[Iterator[Task]], Iterator[Task]]:
        "Returns tasks associated to one or each root"
        if parent is None:
            return iter(tuple())
        if parent is Ellipsis:
            return iter(iter(tsk for tsk in itm.model) for itm in self._items.values())
        return iter(tsk for tsk in self._items[cast(RootTask, parent)].model)

    def cache(self, parent:RootTask, tsk:Optional[Task]):
        "Returns the cache for a given task"
        return self._items[parent].data.getCache(tsk)

    def run(self, parent:RootTask, tsk:Task, copy = False, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        if parent not in self._items:
            return None
        return self._items[parent].run(tsk, copy = copy, pool = pool)

    def processors(self, parent:RootTask, tsk:Task = None) -> Optional[ProcessorController]:
        "Returns a processor for a given root and range"
        ctrl = self._items.get(parent, None)
        return None if ctrl is None else ctrl.keepupto(tsk)

    def instrumenttype(self, parent:RootTask) -> str:
        "return the instrument type"
        return self.track(parent).instrument['type'].name

    @Controller.emit
    def savetrack(self, path: str) -> None:
        "saves the current model"
        items = [item.model for item in self._items.values()]
        ext   = path[path.rfind('.')+1:]
        for obj in self._savers:
            if ext in obj.EXT and obj.save(path, items):
                break
        else:
            raise IOError("Could not save: %s" % str(Path(path).name), 'warning')

    @Controller.emit
    def opentrack(self,
                  task : Union[PATHTYPES, RootTask] = None,
                  model: Iterable[Task]             = tuple()) -> dict:
        "opens a new file"
        tasks = tuple(model)
        if task is None and len(tasks) == 0:
            raise NoEmission()

        elif task is None:
            task = cast(RootTask, tasks[0])

        if not isinstance(task, RootTask):
            lst = openmodels(self._openers, task, tasks)
            for elem in lst[:-1]:
                ctrl = create(elem, processors = self.__processors)
                self._items[cast(RootTask, elem[0])] = ctrl
            task, tasks  = lst[-1][0], lst[-1]

        elif len(tasks) == 0:
            tasks = (task,)

        elif tasks[0] is not task:
            raise ValueError("model[0] ≠ root")

        ctrl = create(*tasks, processors = self.__processors)
        self._items[cast(RootTask, task)] = ctrl
        return dict(controller = self, model = tasks)

    @Controller.emit
    def closetrack(self, task:RootTask) -> dict:
        "opens a new file"
        old = tuple(self._items[task].model)
        del self._items[task]
        return dict(controller = self, task = task, model = old)

    @Controller.emit
    def addtask(self, parent:RootTask, task:Task, index = _none) -> dict:
        "opens a new file"
        old = tuple(self._items[parent].model)
        self._items[parent].add(task, self.__processors[type(task)], index = index)
        return dict(controller = self, parent = parent, task = task, old = old)

    @Controller.emit
    def updatetask(self, parent:RootTask, task:Union[Type[Task],int], **kwargs) -> dict:
        "updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controller.updateModel(tsk, **kwargs)
        self._items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def removetask(self, parent:RootTask, task:Union[Type[Task],int]) -> dict:
        "removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self._items[parent].model)
        self._items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @overload
    def cleardata(self, # pylint: disable=unused-argument,no-self-use
                  parent: '_Ellipsis',
                  task: Task = None) -> dict:
        "clears all cache"

    @overload
    def cleardata(self, # pylint: disable=unused-argument,no-self-use,function-redefined
                  parent: RootTask,
                  task:   Task = None) -> dict:
        "clears parent cache starting at *task*"

    @Controller.emit
    def cleardata(self, parent, task = None) -> dict: # pylint: disable=function-redefined
        "clears all data"
        if parent is Ellipsis:
            self._items.clear()
        elif parent not in self._items:
            raise NoEmission('wrong key')
        elif task is None:
            self._items[cast(RootTask, parent)].clear()
        else:
            self._items[cast(RootTask, parent)].update(task)
        return dict(controller = self, parent = parent, task = Task)

class TaskController(BaseTaskController):
    "Task controller class which knows about globals"
    __readconfig: Any
    __ctrl:       Any
    def setup(self, ctrl):
        "sets up the missing info"
        def _import(name):
            if not isinstance(name, str):
                return name
            modname, clsname = name[:name.rfind('.')], name[name.rfind('.')+1:]
            return getattr(__import__(modname, fromlist = [clsname]), clsname)

        getter = lambda x:    getattr(self, '_'+x)
        setter = lambda x, y: setattr(self, '_'+x, y)
        mdl    = lambda x, y: ctrl.theme.get("tasks.io", x, y)
        if getter('procs') is None:
            setter('procs', register(mdl("processortypes", [])))

        if getter('openers') is None:
            setter('openers', [i(ctrl) for i in mdl("inputtypes", [])])

        if getter('savers') is None:
            setter('savers', [i(ctrl) for i in mdl("outputtypes", [])])

        @ctrl.display.observe
        def _ontasks(old = None, **_):
            if "roottask" in old and mdl("clear", True):
                ctrl.tasks.cleardata(old['roottask'])

        self.__ctrl = ctrl

    def addtask(self, parent:RootTask, task:Task, # pylint: disable=arguments-differ
                index = _none, side = 0):
        "opens a new file"
        if index == 'auto':
            mdl   = self.__ctrl.theme.model("tasks")
            index = mdl.defaulttaskindex(self.tasklist(parent), task, side)
        return super().addtask(parent, task, index)

    def __undos__(self, wrapper):
        "observes all undoable user actions"
        # pylint: disable=unused-variable
        observe = lambda x: self.observe(wrapper(x))

        @observe
        def _onopentrack (controller = None, model = None, **_):
            return partial(controller.closetrack, model[0])

        @observe
        def _onclosetrack(controller = None, model = None, **_):
            return partial(controller.opentrack, model[0], model)

        @observe
        def _onaddtask   (controller = None, parent = None, task = None, **_):
            return partial(controller.removetask, parent, task)

        @observe
        def _onupdatetask(controller = None, parent = None, task = None, old = None, **_):
            return partial(controller.updatetask, parent, task, **old)

        @observe
        def _onremovetask(controller = None, parent = None, task = None, old = None, **_):
            return partial(controller.addtask, parent, task, old.index(task))
