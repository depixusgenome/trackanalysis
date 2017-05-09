#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task controller.

The controller stores:
    - lists of tasks (ProcessorController.model),
    - their associated processors and cache (ProcessorController.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing         import (Union, Iterator, Tuple, # pylint: disable=unused-import
                            Optional, Any, List, Iterable, Dict)
from pathlib        import Path
from itertools      import chain

from model.task     import Task, RootTask, TaskIsUniqueError
from .event         import Controller, NoEmission
from .processor     import Cache, Processor, run as _runprocessors

_m_none = type('_m_none', (), {}) # pylint: disable=invalid-name

class ProcessorController:
    "data and model for tasks"
    __slots__ = ('model', 'data')
    def __init__(self):
        self.model   = []         # type: List[Task]
        self.data    = Cache()

    def task(self, task:Union[Task,int,type], noemission = False) -> Task:
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

    def run(self, tsk:Optional[Task] = None, copy = False, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return _runprocessors(self.data, tsk, copy = copy, pool = pool)

    @classmethod
    def create(cls,
               *models   : Task,
               processors: 'Union[Dict,Iterable[type],type,None]' = Processor
              ) -> 'ProcessorController':
        "creates a task pair for this model"
        tasks = tuple(chain(*(i if isinstance(i, (tuple, list)) else (i,) for i in models)))
        assert all(isinstance(i, Task) for i in tasks)

        pair  = cls()
        if not isinstance(processors, Dict):
            processors = cls.register(processors)

        for other in tasks:
            pair.add(other, processors[type(other)])
        return pair

    @classmethod
    def register(cls,
                 processor: Union[Iterable[type], Processor, None] = None,
                 cache:     Optional[dict]                         = None
                ) -> 'Dict[type,Any]':
        "registers a task processor"
        if cache is None:
            cache = dict()

        if isinstance(processor, Iterable[Processor]):
            for proc in processor:
                cls.register(proc, cache)
            return cache

        elif processor is None:
            return cache

        if isinstance(processor.tasktype, tuple):
            cache.update(dict.fromkeys(processor.tasktype, processor))
        elif processor.tasktype is not None:
            cache[processor.tasktype] = processor

        for sclass in processor.__subclasses__():
            cls.register(sclass, cache)
        return cache

create = ProcessorController.create # pylint: disable=invalid-name

class TaskController(Controller):
    "Data controller class"
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__items   = dict() # type: Dict[RootTask, ProcessorController]
        self.__procs   = dict() # type: Dict[type,Any]
        self.__procs   = (ProcessorController.register(kwargs['processors'])
                          if 'processors' in kwargs else None)

        self.__openers = kwargs.get("openers", None)
        self.__savers  = kwargs.get("savers",  None)

    @property
    def __processors(self):
        if self.__procs is None:
            self.__procs = ProcessorController.register(Processor)
        return self.__procs

    def setup(self, ctrl):
        "sets up the missing info"
        def _import(name):
            if not isinstance(name, str):
                return name
            modname, clsname = name[:name.rfind('.')], name[name.rfind('.')+1:]
            return getattr(__import__(modname, fromlist = (clsname,)), clsname)

        cnf = ctrl.getGlobal('config').tasks
        if self.__procs is None:
            proc         = _import(cnf.processors.get())
            self.__procs = ProcessorController.register(proc)

        if self.__openers is None:
            self.__openers = [_import(itm)(ctrl) for itm in cnf.io.open.get()]

        if self.__savers is None:
            self.__savers  = [_import(itm)(ctrl) for itm in cnf.io.save.get()]

        def _clear(itm):
            if ctrl.getGlobal('config').tasks.clear.get(default = True):
                ctrl.clearData(itm.old)
        ctrl.getGlobal('project').track.observe(_clear)

    def task(self,
             parent : RootTask,
             task   : Union[Task,int,type],
             noemission = False) -> Task:
        "returns a task"
        return self.__items[parent].task(task, noemission = noemission)

    def track(self, parent : Optional[RootTask]):
        "returns the root cache, i;e. the track"
        if parent not in self.__items:
            return None
        track = self.__items[parent].data[0].cache()
        if track is None:
            self.__items[parent].run(parent) # create cache if needed
            track = self.__items[parent].data[0].cache()
        return track

    def tasks(self, task:Optional[RootTask]) -> 'Iterator[Task]':
        "Returns a data object in memory."
        if task is None:
            return iter(tuple())
        if task is Ellipsis:
            return iter(self.tasks(tsk) for tsk in self.__items.keys())
        return iter(tsk for tsk in self.__items[task].model)

    def cache(self, parent:RootTask, tsk:Optional[Task]):
        "Returns the cache for a given task"
        return self.__items[parent].data.getCache(tsk)

    def run(self, parent:RootTask, tsk:Task, copy = False, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return self.__items[parent].run(tsk, copy = copy, pool = pool)

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
                  task : 'Union[None,str,RootTask]' = None,
                  model: Iterable[Task]             = tuple()) -> dict:
        "opens a new file"
        tasks = tuple(model)
        if task is None and len(tasks) == 0:
            raise NoEmission()

        elif task is None:
            task = tasks[0]

        if not isinstance(task, RootTask):
            self.__withopeners(task, tasks)
            raise NoEmission()

        if len(tasks) == 0:
            tasks = (task,)

        elif tasks[0] is not task:
            raise ValueError("model[0] ≠ root")

        self.__items[task] = create(tasks, processors = self.__processors)
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
    def updateTask(self, parent:RootTask, task:Union[Task,int,type], **kwargs) -> dict:
        "updates a task"
        tsk = self.task(parent, task, noemission = True)
        old = Controller.updateModel(tsk, **kwargs)
        self.__items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def removeTask(self, parent:RootTask, task:Union[Task,int,type]) -> dict:
        "removes a task"
        tsk = self.task(parent, task, noemission = True)
        old = tuple(self.__items[parent].model)
        self.__items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old)

    @Controller.emit
    def clearData(self, parent:'Optional[RootTask]' = _m_none) -> dict:
        "clears all data"
        if parent is _m_none:
            self.__items.clear()
        elif parent not in self.__items:
            raise NoEmission('wrong key')
        else:
            self.__items[parent].clear()
        return dict(controller = self, parent = parent)

    def __withopeners(self, task, tasks):
        for obj in self.__openers:
            models = obj.open(task, tasks)
            if models is not None:
                break
        else:
            path = getattr(task, 'path', 'path')
            if path is None or (isinstance(path, (list, tuple))) and len(path) == 0:
                msg  = u"Couldn't open track"

            elif isinstance(path, (tuple, list)):
                msg  = u"Couldn't open: " + Path(str(path[0])).name
                if len(path):
                    msg += ", ..."
            else:
                msg  = u"Couldn't open: " + Path(str(path)).name

            raise IOError(msg, 'warning')

        for elem in models:
            self.openTrack(elem[0], elem)

    @staticmethod
    def __undos__():
        "yields all undoable user actions"
        # pylint: disable=unused-variable
        _1  = None
        def _onOpenTrack(controller = _1, model = _1, **_):
            task = model[0]
            return lambda: controller.closeTrack(task)

        def _onCloseTrack(controller = _1, model = _1, **_):
            return lambda: controller.openTrack(model[0], model)

        def _onAddTask(controller = _1, parent = _1, task = _1, **_):
            return lambda: controller.removeTask(parent, task)

        def _onUpdateTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            return lambda: controller.updateTask(parent, task, **old)

        def _onRemoveTask(controller = _1, parent = _1, task = _1,  old = _1, **_):
            ind = old.index(task)
            return lambda: controller.addTask(parent, task, ind)

        yield from (fcn for name, fcn in locals().items() if name[:3] == '_on')
