#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Processors apply tasks to a data flow"
from    abc             import ABCMeta, abstractmethod
from    functools       import wraps, partial
from    itertools       import chain
from    typing          import (TYPE_CHECKING, Tuple, Callable, Iterable,
                                Iterator, Union, cast)

import  model.task      as     _tasks
from    model.level     import Level

if TYPE_CHECKING:
    from .runner    import Runner # pylint: disable=unused-import

_PROTECTED = ('tasktype',)
class ProtectedDict(dict):
    "Dictionary with read-only keys"
    def __setitem__(self, key, val):
        if key in _PROTECTED and key in self:
            raise KeyError('"{}" is read-only'.format(key))
        else:
            super().__setitem__(key, val)

    def __delitem__(self, key):
        if key in _PROTECTED:
            raise KeyError('"{}" is read-only'.format(key))
        else:
            super().__delitem__(key)

class TaskTypeDescriptor:
    """
    Dynamically finds all Task subclasses implementing
    the __processor__ protocol.
    """
    def __get__(self, obj, tpe) -> Tuple[type, ...]:
        return getattr(tpe, '_tasktypes')()

class MetaProcessor(ABCMeta):
    "Protects attribute tasktype"
    def __new__(mcs, name, bases, nspace): #pylint: disable=arguments-differ
        if name != 'Processor' and 'tasktype' not in nspace:
            tskname = name.replace('Processor', 'Task')
            tsk     = getattr(_tasks, tskname, None)
            cur     = [_tasks.Task]
            while len(cur) and tsk is None:
                tsk = next((i for i in cur if i.__name__ == tskname), None)
                if tsk is None:
                    cur = list(chain(*(i.__subclasses__() for i in cur)))

            assert tsk is not None
            nspace['tasktype'] = tsk

        if isinstance(nspace['tasktype'], type):
            if not issubclass(nspace['tasktype'], _tasks.Task):
                raise TypeError('Only Task classes in the tasktype attribute')
        elif isinstance(nspace['tasktype'], Iterable):
            nspace['tasktype'] = tuple(set(nspace['tasktype']))
            if not all(isinstance(tsk, type) and issubclass(tsk, _tasks.Task)
                       for tsk in nspace['tasktype']):
                raise TypeError('"tasktype" should all be Task classes', str(nspace['tasktype']))
        elif name != 'Processor' and not isinstance(nspace['tasktype'], TaskTypeDescriptor):
            raise AttributeError('"tasktype" must be defined in '+name)
        return super().__new__(mcs, name, bases, nspace)

    def __setattr__(cls, key, value):
        if key in _PROTECTED:
            raise AttributeError('"{}" is read-only'.format(key))
        super().__setattr__(key, value)

class Processor(metaclass=MetaProcessor):
    """
    Main class for processing tasks
    """
    tasktype: Union[type, Tuple[type, ...]] = None
    def __init__(self, task: _tasks.Task = None, **cnf) -> None:
        if task is None:
            task = cast(type, self.tasktype)(**cnf) # pylint: disable=not-callable
        elif isinstance(task, dict):
            tmp  = cast(dict, task)
            tmp.update(cnf)
            task = cast(type, self.tasktype)(**tmp) # pylint: disable=not-callable
        elif not isinstance(task, self.tasktype):
            raise TypeError('"task" must have type '+ str(self.tasktype))
        self.task = task

    @staticmethod
    def canregister():
        "allows discarding some specific processors from automatic registration"
        return True

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
    def beads(_, selected: Iterable[int]) -> Iterable[int]:
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
        else:
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
            cache  = args.data.setCacheDefault(self, dict())
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
        "iterates over possible data"

class ProtocolProcessor(Processor):
    "A processor that can deal with any task having the __processor__ attribute"
    tasktype = cast(Tuple[type, ...], TaskTypeDescriptor())

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
        args.apply(self.apply(**self.config()))

def processors(atask: Union[_tasks.Task, type]) -> Iterator[type]:
    "yields processor types which can handle this task"
    task = type(atask) if not isinstance(atask, type) else atask
    procs = Processor.__subclasses__()
    while len(procs):
        yield from (i for i in procs if issubclass(task, i.tasktype))
        procs = list(chain(*(i.__subclasses__() for i in procs)))
