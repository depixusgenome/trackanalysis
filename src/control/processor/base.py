#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    abc             import abstractmethod
from    functools       import wraps, partial
from    itertools       import chain
from    typing          import (TYPE_CHECKING, TypeVar, Generic, Tuple, Callable, Iterable,
                                Dict, Any, Iterator, Union, cast, Type)

import  model.task      as     _tasks
from    model.level     import Level

if TYPE_CHECKING:
    from .runner    import Runner # pylint: disable=unused-import

class ProcessorException(Exception):
    """
    All exceptions related to a problem with the data should derive from this
    """

class TaskTypeDescriptor:
    """
    Dynamically finds all Task subclasses implementing
    the __processor__ protocol.
    """
    @staticmethod
    def __tasks(base):
        args = getattr(base, '__args__', ())
        if not args:
            return ()

        return tuple(i for i in args
                     if (isinstance(i, cast(type, TypeVar))
                         or (isinstance(i, type) and issubclass(i, _tasks.Task))))

    def __get__(self, obj, tpe) -> Union[type, Tuple[type, ...]]:
        tasks = getattr(tpe, '_tasktypes', None)
        if tasks is None:
            args = (self.__tasks(i) for i in tpe.__orig_bases__)
            task = next((i for i in args if i), None)
            if task is None:
                for cls in tpe.__bases__:
                    if hasattr(cls, 'tasktype'):
                        return cls.tasktype
                raise TypeError(f"Missing Generic specialization in {tpe}")

            return task if len(task) > 1 else task[0]
        return tasks()

TaskType = TypeVar('TaskType', bound = _tasks.Task)
class Processor(Generic[TaskType]):
    """
    Main class for processing tasks
    """
    tasktype = TaskTypeDescriptor()
    def __init__(self, task: Union[Dict[str, Any], TaskType] = None, **cnf) -> None:
        tpe = self.tasktype
        if task is None and isinstance(tpe, type):
            task = cast(type, tpe)(**cnf) # pylint: disable=not-callable
        elif isinstance(task, dict) and isinstance(tpe, type):
            task = cast(type, tpe)(**cast(dict, task), **cnf) # pylint: disable=not-callable
        elif not isinstance(task, self.tasktype):
            raise TypeError('"task" must have type '+ str(self.tasktype))
        self.task: TaskType = cast(TaskType, task)

    @classmethod
    def canregister(cls):
        "allows discarding some specific processors from automatic registration"
        if getattr(cls, '__abstractmethods__', None) or cls.__name__.startswith('Gui'):
            return False
        return not isinstance(cls.tasktype, cast(type, TypeVar))

    @property
    def levelin(self) -> Level:
        "returns the task's input level"
        if hasattr(self.task, 'level'):
            return self.task.level
        return self.task.levelin

    @property
    def levelou(self) -> Level:
        "returns the task's output level"
        if hasattr(self.task, 'level'):
            return self.task.level
        return self.task.levelou

    @property
    def levels(self) -> Tuple[Level,Level]:
        "returns the task's level"
        return (self.levelin, self.levelou)

    def isslow(self) -> bool:
        "wether computations take a long time or not"
        return self.task.isslow()

    @staticmethod
    def beads(cache, selected: Iterable[int]) -> Iterable[int]: # pylint: disable=unused-argument
        "Beads selected/discarded by the task"
        return selected

    @staticmethod
    def canpool():
        "returns whether this is pooled"
        return False

    def config(self) -> dict:
        "Returns a copy of a task's dict"
        return self.task.config()

    def caller(self) -> Callable:
        "Returns an instance of the task's first callable parent class"
        tpe   = type(self.task)
        bases = list(tpe.__bases__)
        while len(bases):
            cls = bases.pop(0)

            if (hasattr(cls, '__call__')
                    and cls.__name__[0] != '_'
                    and not issubclass(cls, _tasks.Task)):
                return cls(**self.task.config())

            bases.extend(cls.__bases__)

        raise TypeError("Could not find a functor base type in "+str(tpe))

    @classmethod
    def newtask(cls, **kwargs) -> _tasks.Task:
        "Returns a copy of a task's dict"
        if callable(cls.tasktype):
            return cls.tasktype(**kwargs) # pylint: disable=not-callable
        raise TypeError("{}.tasktype is not callable".format(cls))

    @classmethod
    def _get_cached(cls, dico, act, frame, item):
        ans = dico.get(item[0], None)
        if ans:
            return item[0], ans

        item          = frame.copy(frame, act(frame, item))
        dico[item[0]] = item[1]
        return item

    @classmethod
    def _setup_cache(cls, cache, action, frame):
        if action is not None:
            frame.withaction(action)
        act = frame.getaction()
        if act is None:
            raise IndexError("Nothing to cache! Set an action prior to mixin")

        dico = cache.setdefault(frame.parents, dict())
        frame.withaction(partial(cls._get_cached, dico, act), clear = True)
        return frame

    @staticmethod
    def cache(fcn):
        """
        Caches actions.

        The cache is specific to the processor instance.
        It will be cleared if any prior task is updated/added/removed.

        The decorated function can return an action. See TrackView.withactions
        for an explanation.

        **Note:** default, the data is copied.

        **Note:** The action's closure must *not* contain a task as this can
        have hard-to-debug side-effects.
        """
        @wraps(fcn)
        def _run(self: 'Processor', args:'Runner'):
            cache  = args.data.setcachedefault(self, dict())
            # pylint: disable=protected-access
            args.apply(partial(self._setup_cache, cache, fcn(self, args)))
        return _run

    @staticmethod
    def action(fcn):
        """
        Adds an action to the currently yielded TrackView.
        The decorated function is expected to return an action.
        See TrackView.withactions for an explanation.

        **Note:** The action's closure must *not* contain a task as this can
        have hard-to-debug side-effects.
        """
        @wraps(fcn)
        def _run(self, args:'Runner'):
            act = fcn(self, args)
            args.apply(lambda frame: frame.withaction(act))
        return _run

    @abstractmethod
    def run(self, args:'Runner'):
        "updates the frames"
        raise NotImplementedError()

ProcCache = Dict[Type[_tasks.Task], Type[Processor]]
def register(proc: Union[None, Type[Processor], Iterable[Type[Processor]]] = None,
             force            = False,
             cache: ProcCache = None,
             recursive        = True) -> ProcCache:
    "returns a register for a given processor"
    if cache is None:
        cache = {}
    procs = (list(proc) if isinstance(proc, (tuple, list)) and proc else
             [proc]     if proc                                     else
             [Processor])
    while len(procs):
        itm = procs.pop(0)
        if isinstance(itm, (list, tuple)):
            procs = list(itm)+procs
            continue
        elif itm is None:
            continue

        if force or itm.canregister():
            ttypes = itm.tasktype
            if isinstance(ttypes, tuple):
                cache.update(dict.fromkeys(ttypes, itm))
            elif ttypes is not None:
                cache[ttypes] = itm

        if recursive and hasattr(itm, '__subclasses__'):
            procs.extend(itm.__subclasses__())
    return cache

class ProtocolProcessor(Processor[TaskType]):
    "A processor that can deal with any task having the __processor__ attribute"
    @staticmethod
    def _tasktypes():
        treating = _tasks.Task.__subclasses__()
        def _run():
            while len(treating):
                cur = treating.pop()
                if hasattr(cur, '__processor__'):
                    yield cur
                treating.extend(cur.__subclasses__())
        return tuple(_run())

    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        fcn = cls.tasktype(**kwa).__processor__() # pylint: disable=not-callable
        return fcn if toframe is None else fcn(toframe)

    def run(self, args:'Runner'):
        "updates the frames"
        args.apply(self.apply(**self.config()))

def processors(atask: Union[_tasks.Task, type]) -> Iterator[type]:
    "yields processor types which can handle this task"
    task = type(atask) if not isinstance(atask, type) else atask
    procs = Processor.__subclasses__()
    while len(procs):
        yield from (i for i in procs if issubclass(task, i.tasktype))
        procs = list(chain(*(i.__subclasses__() for i in procs)))
