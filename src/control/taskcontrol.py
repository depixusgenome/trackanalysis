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

from model.task      import Task, RootTask, TaskIsUniqueError, taskorder, TASK_ORDER
from .event          import Controller, NoEmission
from .processor      import Cache, Processor, run as _runprocessors
from .processor.base import register, CACHE_T
from .taskio         import openmodels

if TYPE_CHECKING:
    from data import Track # pylint: disable=unused-import
    class _Ellipsis:
        pass

_m_none    = type('_m_none', (), {}) # pylint: disable=invalid-name
_M_PROC_T  = Type[Processor]
_M_PROCS_T = Union[Iterable[_M_PROC_T], _M_PROC_T]
PATHTYPE   = Union[str, Path]
PATHTYPES  = Union[PATHTYPE,Tuple[PATHTYPE,...]]

class ProcessorController:
    "data and model for tasks"
    __slots__ = ('model', 'data', 'copy')
    def __init__(self, copy = False):
        self.model: List[Task] = []
        self.data              = Cache()
        self.copy              = copy

    def task(self, task:Union[Type[Task],int], noemission = False) -> Task:
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

    def add(self, task, proctype, index = _m_none):
        "adds a task to the list"
        TaskIsUniqueError.verify(task, self.model)
        proc = proctype(task)

        if index is _m_none:
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

    def keepupto(self, tsk:Task = None) -> 'ProcessorController':
        "Returns a processor for a given root and range"
        ind         = None if tsk is None else self.data.index(tsk)
        other       = type(self)(copy = self.copy)
        other.model = self.model[:None if ind is None else ind+1]
        other.data  = self.data.keepupto(ind)
        return other

    @classmethod
    def create(cls, *models : Task, processors: Union[Dict,_M_PROCS_T,None] = Processor
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
                 processor: _M_PROCS_T = None,
                 cache:     CACHE_T    = None,
                 force                 = False,
                ) -> Dict[Type[Task], Type[Processor]]:
        "registers a task processor"
        return register(processor, force, cache, True)

create   = ProcessorController.create # pylint: disable=invalid-name

class BaseTaskController(Controller):
    "Data controller class"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__items: Dict[RootTask, ProcessorController] = dict()
        self.__procs: Dict[Type[Task], Type[Processor]]   = dict()
        self.__procs = (register(kwargs['processors'])
                        if 'processors' in kwargs else None)

        self.__openers = kwargs.get("openers", None)
        self.__savers  = kwargs.get("savers",  None)

    @property
    def __processors(self):
        if self.__procs is None:
            self.__procs = register(Processor)
        return self.__procs

    def task(self,
             parent : Optional[RootTask],
             task   : Union[Type[Task], int],
             noemission = False) -> Task:
        "returns a task"
        ctrl = ProcessorController() if parent is None else self.__items[parent]
        return ctrl.task(task, noemission = noemission)

    @overload
    def track(self, parent: None) -> None: # pylint: disable=no-self-use,unused-argument
        "returns None"

    @overload
    def track(self, # pylint: disable=no-self-use,unused-argument,function-redefined
              parent: RootTask) -> 'Track':
        "returns the root cache, i;e. the track"

    @overload
    def track(self, # pylint: disable=no-self-use,unused-argument,function-redefined
              parent: '_Ellipsis') -> Iterator['Track']:
        "returns all root cache, i;e. tracks"

    def track(self, parent): # pylint: disable=function-redefined
        "returns the root cache, i;e. the track"
        if parent is Ellipsis:
            return (i.data[0].cache() for i in self.__items.values())

        if parent not in self.__items:
            return None
        track = self.__items[parent].data[0].cache()
        if track is None:
            self.__items[parent].run(parent) # create cache if needed
            track = self.__items[parent].data[0].cache()
        return track

    def tasks(self, parent: Union[None, '_Ellipsis', RootTask]
             ) -> Union[Iterator[Iterator[Task]], Iterator[Task]]:
        "Returns tasks associated to one or each root"
        if parent is None:
            return iter(tuple())
        if parent is Ellipsis:
            return iter(iter(tsk for tsk in itm.model) for itm in self.__items.values())
        return iter(tsk for tsk in self.__items[cast(RootTask, parent)].model)

    def cache(self, parent:RootTask, tsk:Optional[Task]):
        "Returns the cache for a given task"
        return self.__items[parent].data.getCache(tsk)

    def run(self, parent:RootTask, tsk:Task, copy = False, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        if parent not in self.__items:
            return None
        return self.__items[parent].run(tsk, copy = copy, pool = pool)

    def processors(self, parent:RootTask, tsk:Task = None) -> Optional[ProcessorController]:
        "Returns a processor for a given root and range"
        ctrl = self.__items.get(parent, None)
        return None if ctrl is None else ctrl.keepupto(tsk)

    @Controller.emit
    def saveTrack(self, path: str) -> None:
        "saves the current model"
        items = [item.model for item in self.__items.values()]
        ext   = path[path.rfind('.')+1:]
        for obj in self.__savers:
            if ext in obj.EXT and obj.save(path, items):
                break
        else:
            raise IOError("Could not save: %s" % str(Path(path).name), 'warning')

    @Controller.emit
    def openTrack(self,
                  task : Union[PATHTYPES, RootTask] = None,
                  model: Iterable[Task]             = tuple()) -> dict:
        "opens a new file"
        tasks = tuple(model)
        if task is None and len(tasks) == 0:
            raise NoEmission()

        elif task is None:
            task = cast(RootTask, tasks[0])

        if not isinstance(task, RootTask):
            lst = openmodels(self.__openers, task, tasks)
            for elem in lst[:-1]:
                ctrl = create(elem, processors = self.__processors)
                self.__items[cast(RootTask, elem[0])] = ctrl
            task, tasks  = lst[-1][0], lst[-1]

        elif len(tasks) == 0:
            tasks = (task,)

        elif tasks[0] is not task:
            raise ValueError("model[0] ≠ root")

        ctrl = create(tasks, processors = self.__processors)
        self.__items[cast(RootTask, task)] = ctrl
        return dict(controller = self, model = tasks)

    @Controller.emit
    def closeTrack(self, task:RootTask) -> dict:
        "opens a new file"
        old = tuple(self.__items[task].model)
        del self.__items[task]
        return dict(controller = self, task = task, model = old)

    @Controller.emit
    def addTask(self, parent:RootTask, task:Task, index = _m_none) -> dict:
        "opens a new file"
        old = tuple(self.__items[parent].model)
        self.__items[parent].add(task, self.__processors[type(task)], index = index)
        return dict(controller = self, parent = parent, task = task, old = old)

    @Controller.emit
    def updateTask(self, parent:RootTask, task:Union[Type[Task],int], **kwargs) -> dict:
        "updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controller.updateModel(tsk, **kwargs)
        self.__items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def removeTask(self, parent:RootTask, task:Union[Type[Task],int]) -> dict:
        "removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self.__items[parent].model)
        self.__items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @overload
    def clearData(self, # pylint: disable=unused-argument,no-self-use
                  parent: '_Ellipsis',
                  task: Task = None) -> dict:
        "clears all cache"

    @overload
    def clearData(self, # pylint: disable=unused-argument,no-self-use,function-redefined
                  parent: RootTask,
                  task:   Task = None) -> dict:
        "clears parent cache starting at *task*"

    @Controller.emit
    def clearData(self, parent, task = None) -> dict: # pylint: disable=function-redefined
        "clears all data"
        if parent is Ellipsis:
            self.__items.clear()
        elif parent not in self.__items:
            raise NoEmission('wrong key')
        elif task is None:
            self.__items[cast(RootTask, parent)].clear()
        else:
            self.__items[cast(RootTask, parent)].update(task)
        return dict(controller = self, parent = parent, task = Task)

class TaskController(BaseTaskController):
    "Task controller class which knows about globals"
    def __init__(self, **kwa):
        super().__init__(**kwa)
        self.__order:      Any = None
        self.__readconfig: Any = None

    def setup(self, ctrl):
        "sets up the missing info"
        def _import(name):
            if not isinstance(name, str):
                return name
            modname, clsname = name[:name.rfind('.')], name[name.rfind('.')+1:]
            return getattr(__import__(modname, fromlist = [clsname]), clsname)

        getter = lambda x:    getattr(self, '_BaseTaskController__'+x)
        setter = lambda x, y: setattr(self, '_BaseTaskController__'+x, y)
        cnf    = ctrl.globals.config.tasks
        if getter('procs') is None:
            proc = _import(cnf.processors.get())
            setter('procs', register(proc))

        if getter('openers') is None:
            setter('openers', [_import(itm)(ctrl) for itm in cnf.io.open.get()])

        if getter('savers') is None:
            setter('savers', [_import(itm)(ctrl) for itm in cnf.io.save.get()])

        self.__order         = ctrl.globals.config.tasks.order
        self.__order.default = list(TASK_ORDER)

        def _clear(itm):
            if ctrl.globals.config.tasks.clear.get(default = True):
                ctrl.clearData(itm.old)
        ctrl.globals.project.track.observe(_clear)

        self.__readconfig = ctrl.readconfig

    def defaulttaskindex(self, parent:RootTask, task:Type[Task], side = 0) -> int:
        "returns the default task index"
        if not isinstance(task, type):
            task = type(task)
        order    = tuple(taskorder(self.__order.get()))
        previous = order[:order.index(task)+side]

        curr     = tuple(cast(Iterator[Task], self.tasks(parent)))
        for i, tsk in enumerate(curr[1:]):
            if not isinstance(tsk, previous):
                return i+1
        return len(curr)

    def openTrack(self,
                  task : Union[str, RootTask, Dict[str,str]] = None,
                  model: Union[dict, Iterable[Task]]         = tuple()):
        if isinstance(model, dict):
            assert task is None
            if len(model.get('tasks', (()))[0]):
                super().openTrack(model = model.pop("tasks")[0])
                self.__readconfig(model)
        else:
            super().openTrack(task, cast(Iterable[Task], model))

    def addTask(self, parent:RootTask, task:Task, # pylint: disable=arguments-differ
                index = _m_none, side = 0):
        "opens a new file"
        if index == 'auto':
            index = self.defaulttaskindex(parent, cast(Type[Task], task), side)
        return super().addTask(parent, task, index)

    @staticmethod
    def __undos__():
        "yields all undoable user actions"
        # pylint: disable=unused-variable
        def _onOpenTrack (controller = None, model = None, **_2):
            return partial(controller.closeTrack, model[0])

        def _onCloseTrack(controller = None, model = None, **_2):
            return partial(controller.openTrack, model[0], model)

        def _onAddTask   (controller = None, parent = None, task = None, **_2):
            return partial(controller.removeTask, parent, task)

        def _onUpdateTask(controller = None, parent = None, task = None, old = None, **_):
            return partial(controller.updateTask, parent, task, **old)

        def _onRemoveTask(controller = None, parent = None, task = None, old = None, **_):
            return partial(controller.addTask, parent, task, old.index(task))

        yield from (fcn for name, fcn in locals().items() if name[:3] == '_on')
