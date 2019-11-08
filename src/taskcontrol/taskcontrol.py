#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task controller.

The controller stores:
    - lists of tasks (ProcessorController.model),
    - their associated processors and cache (ProcessorController.data).

It can add/delete/update tasks, emitting the corresponding events
"""
from typing          import (
    Union, Iterator, Type, cast, Tuple, Optional, Any, List, Iterable, Dict,
    overload, TYPE_CHECKING
)
from pathlib         import Path
from functools       import partial

from taskmodel              import Task, RootTask
from taskmodel.application  import TasksConfig
from taskmodel.processors   import TaskCacheList, appendtask
from control.event          import Controller, NoEmission
from .processor             import Cache, Processor, run as _runprocessors
from .processor.base        import register, ProcCache
from .taskio                import openmodels

if TYPE_CHECKING:
    from data import Track  # pylint: disable=unused-import

    class _Ellipsis:
        pass

_Proc     = Type[Processor]
_Procs    = Union[Iterable[_Proc], _Proc]
_ProcDict = Union[Dict[Type[Task], Processor],_Procs,None]
PATHTYPE  = Union[str, Path]
PATHTYPES = Union[PATHTYPE,Tuple[PATHTYPE,...]]

class ProcessorController(TaskCacheList):
    "data and model for tasks"
    def __init__(self, copy = True):
        super().__init__(copy)
        self.data = Cache()

    def task(self, task:Union[Type[Task],int], noemission = False) -> Optional[Task]:
        "returns a task"
        try:
            return super().task(task, noemission)
        except KeyError as exc:
            raise NoEmission("missing task") from exc

    def run(self, tsk:Task = None, copy = None, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        return _runprocessors(self.data, tsk,
                              copy = self.copy if copy is None else copy,
                              pool = pool)

    @classmethod
    def create(cls, *models: Task, processors: _ProcDict = None) -> 'ProcessorController':
        """
        Creates a ProcessorController containing a list of task-processor pairs.

        Parameters:
        -----------
        models: Tuple[Task]
            a sequence of tasks
        processors: Dict[Type[Task], Processor], Iterable[Type[Processor]] or None
            this argument allows defining which processors to use for implementing
            the provided tasks
        """
        tasks: List[Task] = []
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
    def register(
            cls,
            processor: _Procs     = None,
            cache:     ProcCache  = None,
            force                 = False,
    ) -> Dict[Type[Task], Type[Processor]]:
        "registers a task processor"
        return register(processor, force, cache, True)


create   = ProcessorController.create  # pylint: disable=invalid-name

def process(
        *models: Task,
        processors: _ProcDict = Processor,
        output: str = 'items'
) -> Iterator:
    """
    Creates a ProcessorController, runs it and returns a chained iterator
    of all its outputs.

    # Parameters:

    * model: Tuple[Task]
        a sequence of tasks
    * processors: Iterable[Type[Processor]] or Dict[Type[task], Processor]
        this argument allows defining which processors to use for implementing
        the provided tasks
    * output: "items", "values" or "keys"
        whether to return key-value pairs, values only or keys only, respectively.
    """
    assert output in {'items', 'values', 'keys'}
    return (
        j
        for i in create(*models, processors = processors).run()
        for j in (i if output == 'items' else getattr(i, output)())
    )

class BaseTaskController(Controller):  # pylint: disable=too-many-public-methods
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

    def processortype(self, task: Union[Task, Type[Task]]) -> Type[Processor]:
        "return the type of processor to use"
        if task is ...:
            return self.__processors
        return self.__processors[task if isinstance(task, type) else type(task)]

    def task(
            self,
            parent:     Optional[RootTask],
            task:       Union[Type[Task], int],
            noemission: bool = False
    ) -> Optional[Task]:
        "returns a task"
        ctrl = self._items[parent] if parent in self._items else ProcessorController()
        return ctrl.task(task, noemission = noemission)

    @overload
    def track(self, parent: None) -> None:
        "returns None"

    @overload
    def track(self, parent: RootTask) -> 'Track':               # noqa
        "returns the root cache, i;e. the track"

    @overload
    def track(self, parent: '_Ellipsis') -> Iterator['Track']:  # type: ignore # noqa
        "returns all root cache, i;e. tracks"

    def track(self, parent):                                    # noqa
        "returns the root cache, i;e. the track"
        if parent is Ellipsis:
            return (i.data[0].cache() for i in self._items.values())

        if parent not in self._items:
            return None

        track = self._items[parent].data[0].cache()
        if track is None:
            self._items[parent].run(parent)  # create cache if needed
            track = self._items[parent].data[0].cache()
        return track

    def tasklist(
            self, parent: Union[None, '_Ellipsis', RootTask]
    ) -> Union[Iterator[Iterator[Task]], Iterator[Task]]:
        "Returns tasks associated to one or each root"
        if parent is None:
            return iter(tuple())
        if parent is Ellipsis:
            return iter(iter(tsk for tsk in itm.model) for itm in self._items.values())
        return iter(tsk for tsk in self._items[cast(RootTask, parent)].model)

    def cache(self, parent:RootTask, tsk:Optional[Task]):
        "Returns the cache for a given task"
        return self._items[parent].data.getcache(tsk)

    def run(self, parent:RootTask, tsk:Task, copy = False, pool = None):
        """
        Iterates through the list up to and including *tsk*.
        Iterates through all if *tsk* is None
        """
        if parent not in self._items:
            return None
        return self._items[parent].run(tsk, copy = copy, pool = pool)

    def processors(
            self, parent:RootTask, tsk:Task = None, copy:bool = True
    ) -> Optional[ProcessorController]:
        "Returns a processor for a given root and range"
        ctrl = self._items.get(parent, None)
        assert copy or tsk is None
        return None if ctrl is None else ctrl.keepupto(tsk) if copy else ctrl

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
                  task:  Union[PATHTYPES, RootTask] = None,
                  model: Iterable[Task]             = tuple()) -> dict:
        "opens a new file"
        tasks = tuple(model)
        if task is None and len(tasks) == 0:
            raise NoEmission()

        if task is None:
            task = cast(RootTask, tasks[0])

        lst: List[Tuple[bool, Tuple[Task,...]]] = (
            openmodels(self._openers, task, tasks) if not isinstance(task, RootTask) else
            [(False, (task,))] if len(tasks) == 0    else
            [(True, tasks)]    if tasks[0] is task   else
            []
        )
        ctrls: List[Tuple[bool, ProcessorController]] = [
            (isarch, create(elem, processors = self.__processors))
            for isarch, elem in lst
        ]

        if ctrls:
            self.handle(
                "openingtracks",
                self.emitpolicy.outasdict,
                {'controller': self, 'models': ctrls}
            )

        if not ctrls:
            raise NoEmission()

        self._items.update({cast(RootTask, ctrl.model[0]): ctrl for _, ctrl in ctrls})
        return dict(
            controller = self,
            model      = ctrls[-1][1].model,
            isarchive  = ctrls[-1][0],
            taskcache  = ctrls[-1][1]
        )

    @Controller.emit
    def closetrack(self, task:RootTask) -> dict:
        "opens a new file"
        old = tuple(self._items[task].model)
        del self._items[task]
        new = next(iter(self._items.values()), ProcessorController())
        return dict(controller = self, task = task, model = old, new = new)

    @Controller.emit
    def addtask(self, parent:RootTask, task:Task, index = appendtask) -> dict:
        "opens a new file"
        old   = tuple(self._items[parent].model)
        cache = self._items[parent].add(task, self.__processors[type(task)], index = index)
        return dict(controller = self, parent = parent, task = task, old = old, cache = cache)

    @Controller.emit
    def updatetask(self, parent:RootTask, task:Union[Type[Task],int], **kwargs) -> dict:
        "updates a task"
        tsk   = self.task(parent, task, noemission = True)
        old   = Controller.updatemodel(tsk, **kwargs)
        cache = self._items[parent].update(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old, cache = cache)

    @Controller.emit
    def removetask(self, parent:RootTask, task:Union[Type[Task],int]) -> dict:
        "removes a task"
        tsk   = self.task(parent, task, noemission = True)
        old   = tuple(self._items[parent].model)
        cache = self._items[parent].remove(tsk)
        return dict(controller = self, parent = parent, task = tsk, old = old, cache = cache)

    @overload
    def cleardata(self, parent: '_Ellipsis', task: Task = None) -> dict:    # noqa
        "clears all cache"

    @overload
    def cleardata(self, parent: RootTask, task: Task = None) -> dict:       # noqa
        "clears parent cache starting at *task*"

    @Controller.emit
    def cleardata(self, parent, task = None) -> dict:
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
    __readconfig:  Any
    __tasksconfig: TasksConfig

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__tasksconfig = TasksConfig()

    def setup(self, ctrl):
        "sets up the missing info"
        self.__tasksconfig = ctrl.theme.swapmodels(self.__tasksconfig)

        def _import(name):
            if not isinstance(name, str):
                return name
            modname, clsname = name[:name.rfind('.')], name[name.rfind('.')+1:]
            return getattr(__import__(modname, fromlist = [clsname]), clsname)

        def mdl(attr: str, dflt):
            "return the model attribute value"
            return ctrl.theme.get("tasks.io", attr, dflt)

        if getattr(self, '_procs') is None:
            setattr(self, '_procs', register(mdl("processortypes", [])))

        if getattr(self, '_openers') is None:
            setattr(self, '_openers', [i(ctrl) for i in mdl("inputtypes", [])])

        if getattr(self, '_savers') is None:
            setattr(self, '_savers', [i(ctrl) for i in mdl("outputtypes", [])])

        @ctrl.display.observe
        @ctrl.display.hashwith(self)
        def _ontasks(old, **_):
            if "taskcache" in old and mdl("clear", True) and old['taskcache'].model:
                ctrl.tasks.cleardata(old['taskcache'].model[0])

    def addtask(  # pylint: disable=arguments-differ
            self,
            parent: RootTask,
            task:   Task,
            index = appendtask,
            side  = 0
    ):
        "opens a new file"
        if index == 'auto':
            index = self.__tasksconfig.defaulttaskindex(self.tasklist(parent), task, side)
        return super().addtask(parent, task, index)

    def __undos__(self, wrapper):
        "observes all undoable user actions"

        def observe(fcn):
            "add an observer"
            return self.observe(wrapper(fcn))

        @observe
        def _onopentrack(controller, model, **_):
            return partial(controller.closetrack, model[0])

        @observe
        def _onclosetrack(controller, model, **_):
            return partial(controller.opentrack, model[0], model)

        @observe
        def _onaddtask(controller, parent, task, **_):
            return partial(controller.removetask, parent, task)

        @observe
        def _onupdatetask(controller, parent, task, old, **_):
            return partial(controller.updatetask, parent, task, **old)

        @observe
        def _onremovetask(controller, parent, task, old, **_):
            return partial(controller.addtask, parent, task, old.index(task))
