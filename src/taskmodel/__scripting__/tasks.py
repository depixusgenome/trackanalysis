#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkeypatches tasks and provides a simpler access to usual tasks
"""
from pathlib                  import Path
from functools                import partial
from typing                   import (Type, Tuple, List, Callable, Dict, Any,
                                      Optional, cast)
from concurrent.futures       import ProcessPoolExecutor

from copy                     import deepcopy
from enum                     import Enum, _EnumDict # type: ignore

import taskstore
from data.views                  import TrackView
from data.track                  import Track
from taskcontrol.taskcontrol     import create as _create, ProcessorController
from taskcontrol.processor.base  import Processor, register
from taskcontrol.processor.utils import ActionTask
from utils                       import update
from utils.decoration            import addto
from utils.attrdefaults          import toenum
from taskmodel                   import Task, Level
from taskmodel.application       import TasksConfig
from taskmodel.track             import InMemoryTrackTask

def _update(self, *args, **kwa):
    info = dict(*args, **kwa)
    for i, j in info.items():
        self[i] = j
_EnumDict.update = _update # correcting a python bug

for name in ('cleaning.processor', 'cordrift', 'eventdetection.processor',
             'peakfinding.processor', 'peakcalling.processor'):
    __import__(name+'.__config__')

_CNV = dict([('cleaning', 'datacleaning'), ('alignment', 'extremumalignment'),
             ('minbiasalignment', 'minbiaspeakalignment'), ('cycles', 'cyclecreator'),
             ('subtraction', 'beadsubtraction'), ('selection', 'dataselection'),
             ('peakalignment', 'peakcorrelationalignment')])

_CNF           = {i: type(j) for i, j in TasksConfig.picotwist.items()}
_CNF['action'] = ActionTask
for _i in _CNV.items():
    _CNF[_i[0]] = _CNF.pop(_i[1])

class _DOCHelper(Enum):
    # pylint: disable=bad-continuation
    trackreader    = ("reads a track file",)
    cyclesampling  = ("transforms a track into one containing only a selection of cycle.",)
    action         = (
        "a Callable[[TrackView, Tuple[KEY, DATA]], Tuple[KEY, Any]]",
        " which transforms each input indivually"
        )
    subtraction    = (
        "if one or more fixed beads has been indicated,",
        "subtracts from the current bead the median signal per frame of the",
        "fixed beads.")
    cleaning       = (
        "aberrant values and cycles are discarded using the",
        "the rules defined in the `cleaning.processor.DataCleaningTask` task.")
    selection      = ("allows selecting/discarding specific beads and or cycles",)
    alignment      = (
        "the cycles are aligned using the algorithm defined",
        "in the `eventdetection.processor.alignment.ExtremumAlignmentTask` task.")
    clipping       = (
        "PHASE.measure data above PHASE.pull and below PHASE.initial is clipped",
        "as found in `cleaning.processor.ClippingTask` task.")
    driftperbead   = (
        "recomputes an *average fixed bead* cycle from all cycles in a bead",
        "and subtracts it from all cycles in the bead"
        )
    driftpercycle  = (
        "recomputes an *average fixed bead* from all beads",
        "and subtracts it from all cycles in the bead"
        )
    cycles         = ("returns a Cycles view",)
    eventdetection = (
        "flat events are detected in `PHASE.measure`",
        "and returned per cycle.")
    peakalignment  = ("Aligns cycles using events in `PHASE.measure`",)
    peakselector   = (
        "events are grouped per peak. The list of peaks",
        "is returned per bead.")
    minbiasalignment = ("Aligns cycles using events in peaks",)
    singlestrand   = (
        "The single-strand peak is detected (using the closing patterns in",
        "the `PHASE.rampdown`) and removed from the list of peaks")
    fittohairpin   = (
        "the z-axis is aligned with theoretical positions",
        "using a rigid transformation.")
    fittoreference = (
        "transforms the z-axis to fit the extension from the same bead in",
        "another experiment."
        )
    beadsbyhairpin = ("beads identified as the same hairpin are grouped together",)
    dataframe      = ("transforms the whole frame to a `pandas.DataFrame`",)

    def tostring(self) -> str:
        "returns the doc as a single string"
        return ' '.join(self.value)

    @classmethod
    def todoc(cls, *args:str, indent = 4) -> str:
        "return a string concatenating the docs from provided arguments"
        if len(args) == 0:
            args = tuple(cls.__members__.keys())
        string = ' '*indent+'* `Tasks.{key}`: {value}\n'
        space  = ' '*(indent*2)
        return '\n'+''.join(string.format(key   = i,
                                          value = space.join(getattr(cls, i).value))
                            for i in args)

    @classmethod
    def add(cls, *args:str, indent = 4, header = None) -> Callable[[Callable], Callable]:
        "decorator for adding doc"
        doc = cls.todoc(*args, indent = indent)
        if header:
            doc = header+ "\n\n" + doc

        def _wrapper(fcn):
            if hasattr(fcn, '__doc__'):
                if getattr(fcn, '__doc__'):
                    fcn.__doc__ += doc
                else:
                    fcn.__doc__ = doc
            return fcn
        return _wrapper

class Tasks(Enum):
    """
    Most available tasks can be created using this class:

    ### Task Creation

    These can be created as follows:

    ```python
    >>> task = Tasks.alignment()
    >>> assert isinstance(task, ExtremumAlignmentTask)
    ```

    Attribute values can be set:

    ```python
    >>> assert Tasks.peakselector().align is not None         # default value
    >>> assert Tasks.peakselector(align = None).align is None # change default
    >>> assert Tasks.peakselector('align').align is not None  # back to true default
    ```

    or:

    ```python
    >>> assert Tasks.peakselector(align = None).align is None # change default
    >>> assert Tasks.peakselector(align = Tasks.RESET).align is not None  # back to true default
    ```

    It's also possible to set sub-fields:

    ```python
    >>> assert Tasks.peakselector().group.mincount == 5
    >>> assert Tasks.peakselector({'group.mincount': 2}).group.mincount == 2
    >>> assert Tasks.peakselector({'group.mincount': 2}).group.mincount == 2
    ```

    ### Creating a List of Tasks

    A method `Tasks.apply` allows creating a list of tasks. The first argument
    can be a path to the data or even a '.ana' file. In the latter case, no other
    arguments are accepted.

    Other arguments allow creating other tasks. The arguments are either:

    * a `Tasks` enum value,
    * a `Task` instance
    * a callable, in which case an `ActionTask` is created.

    For example, to create aligned events and change their stretch and bias:

    ```python
    >>> def fcn(stretch, bias, info):
    ...     info['data'][:] = [(i-bias)*stretch for i in info['data']]
    >>> Tasks.apply("my path to data",
    ...             Tasks.alignment, Tasks.eventdetection,
    ...             lambda i: fcn(2., .5, i),
    ...             Tasks.peakalignment)
    ```

    or:

    ```python
    >>> Tasks.apply("my path to data",
    ...             Tasks.alignment, Tasks.eventdetection,
    ...             Task.action(fcn, 2., .5),
    ...             Tasks.peakalignment)
    ```

    The keyword `pool` allows providing a specific `ProcessPoolExecutor`. If provided with
    `pool == True`, the `ProcessPoolExecutor` instance is created and used.
    """
    locals().update({i:i for i in _CNF})

    @staticmethod
    def classes() -> Dict[str, Type[Task]]:
        "returns default tasks"
        return _CNF

    def default(self, mdl = None) -> Task:
        "returns default tasks"
        return (TasksConfig.picotwist if mdl is None else
                getattr(TasksConfig, mdl.instrument))[self._cnv(self.name)]

    @staticmethod
    def _cnv(key: Optional[str]):
        return _CNV if key is None else _CNV.get(key, key)

    def tasktype(self) -> Type[Task]:
        "returns the task type"
        return self.classes()[self.name]

    @classmethod
    def create(cls, *args, **kwa):
        "returns the task associated to the argument"
        return (cls.__create(args[0], kwa) if len(args) == 1 else
                [cls.__create(i, kwa) for i in args])

    @classmethod
    def defaulttaskorder(cls, order = None) -> Tuple[Type[Task],...]:
        """
        Creates a list of tasks in the default order.

        This order is defined in `Tasks.__taskorder__()`.
        """
        if order is None:
            order =  cls.__taskorder__()
        items = tuple(type(cls(i)()) for i in order[::-1])
        return cast(Tuple[Type[Task],...], items[::-1])

    @classmethod
    def defaulttasklist(cls, obj, upto, cleaned:bool = None) -> List[Task]:
        """
        Returns a default task list depending on the type of raw data.

        The list is computed:

        1. using tasks in `Tasks.__tasklist__()`
        2. adding tasks in `Tasks.__cleaning__()` *unless* the track is *clean*.
        3. keep only those tasks in `Tasks.__nodefault__()` which don't have
        only default values for their attributes.
        """
        tasks = list(cls.__tasklist__()) # type: ignore
        paths = getattr(obj, 'path', obj)
        if (getattr(obj, 'cleaned', cleaned)
                or (isinstance(paths, (tuple, list)) and len(paths) > 1)):
            tasks = [i for i in tasks if i not in cls.__cleaning__()] # type: ignore

        upto  = cls(upto) if upto is not None and upto is not Ellipsis else Ellipsis
        itms  = (tasks if upto is Ellipsis  else
                 ()    if upto not in tasks else
                 tasks[:tasks.index(upto)+1])
        nod   = cls.__nodefault__()
        isdef = lambda i: i == type(i)()
        return [i() for i in itms if i not in nod or not isdef(i())] # type: ignore

    @classmethod
    @_DOCHelper.add(header = "These can be:")
    def tasklist(cls, *tasks, **kwa) -> List[Task]:
        "Return as create except that a list may be completed as necessary"
        if len(tasks) == 1 and isinstance(tasks[0], (str, Path)):
            mdl = taskstore.load(tasks[0])
            if mdl is None:
                raise ValueError("Could not load model")
            return mdl

        if Ellipsis in tasks:
            if Ellipsis is not tasks[1]:
                raise NotImplementedError("... must be second place in Tasks.tasklist")
            first = cls.get(tasks[0], **kwa)
            tmp   = cls.get(*tasks[2:], **kwa)
            last  = cast(List[Task], [tmp] if isinstance(tmp, Task) else tmp)
            sec   = Tasks(last[0])
            if sec not in cls.__tasklist__():
                raise RuntimeError("First task after ... must be part of Tasks.defaulttasklist")
            lst = [first] + list(cls.defaulttasklist(tasks[0], sec))[:-1] + last
        else:
            tmp = cls.get(*tasks, **kwa)
            lst = cast(List[Task], [tmp] if isinstance(tmp, Task) else tmp)

        torder = cls.defaulttaskorder()[::-1]
        for i, itm in enumerate(torder[:-1]):
            ind = next((i for i, j in enumerate(lst) if isinstance(j, itm)), None)
            if ind is None:
                continue

            ival = ind
            while ival > 0 and getattr(lst[ival-1], 'level', None) is Level.none:
                ival -= 1
            if ival == 0 or not isinstance(lst[ival-1], torder[i+1]):
                lst.insert(ind, cls._missing_(torder[i+1])(**kwa))
        return lst

    @classmethod
    @_DOCHelper.add(header = "These can be:")
    def processors(cls, *args, copy = True) -> ProcessorController:
        "Return a `ProcessorController` containing selected tasks."
        procs      = _create(*cls.tasklist(*args))
        procs.copy = copy
        return procs


    def dumps(self, **kwa):
        "returns the json configuration"
        kwa.setdefault('saveall', False)
        kwa.setdefault('indent', 4)
        kwa.setdefault('ensure_ascii', False)
        kwa.setdefault('sort_keys', True)
        kwa.setdefault('patch', None)
        return taskstore.dumps(self, **kwa)

    def processor(self, *resets, **kwa) -> Processor:
        "Returns the default processor for this task"
        task  = self(*resets, **kwa)
        return register(None)[type(task)](task = task)

    def __call__(self, *resets, **kwa)-> Task:
        return getattr(self, '_default_'+self.name, self._default_call)(*resets, **kwa)

    class _TaskGetter:
        def __get__(self, obj, tpe):
            return tpe.create if obj is None else obj

    get = _TaskGetter()

    class _TaskApply:
        def __get__(self, obj, tpe):
            # pylint: disable=protected-access
            return tpe._apply_cls if obj is None else obj._apply_self
    apply = _TaskApply()

    def _apply_self(self, toframe: TrackView = None, # pylint: disable=keyword-arg-before-vararg
                    *resets, **kwa) -> TrackView:
        """
        Applies the task to the frame
        """
        proc = self.processor(*resets, **kwa)
        return getattr(proc, 'apply')(toframe, **proc.config())

    @classmethod
    @_DOCHelper.add(header = "These can be:")
    def _apply_cls(cls, *args, copy = True, pool = None) -> TrackView:
        "Return an iterator over the result of selected tasks."
        procs = cls.processors(*args)
        ret   = isinstance(pool, bool)
        if ret:
            pool = ProcessPoolExecutor()

        out = next(iter(procs.run(copy = copy, pool = pool)))
        if ret:
            with pool:
                out = tuple(out)
        return out

    @staticmethod
    def _default_action(*args, **kwa):
        call = kwa.pop('call', None)
        if len(args) >= 1 and call is None:
            call, args = args[0], args[1:]

        if call is None:
            assert False
            return ActionTask()

        if not callable(call):
            raise RuntimeError("Incorrect action")

        if len(args) > 0 or len(kwa):
            call = partial(call, *args, **kwa)
        return ActionTask(call = call)

    def _default_trackreader(self, *args, **kwa):
        if len(args) == 1 and isinstance(args[0], Track):
            cnf = args[0].__getstate__()
            cnf.update(**kwa)
            kwa = cnf

        paths = [i for i in args if isinstance(i, Path)]
        args  = tuple(i for i in args if not isinstance(i, Path))
        if paths:
            kwa['path'] = paths

        return self._default_call(*args, **kwa)

    def _default_call(self, *resets, **kwa) -> Task:
        current = kwa.pop('current', None)
        cnf     = self.default() if current is None else deepcopy(current)
        if Ellipsis in resets:
            resets = tuple(i for i in resets if i is not Ellipsis)

        kwa.update({i: getattr(type(cnf), i) for i in resets if isinstance(i, str)})

        state = cnf.__getstate__() if hasattr(cnf, '__getstate__') else deepcopy(cnf.__dict__)
        state.update(**kwa)
        task  = cnf.__class__(**state)

        for key, value in next((i for i in resets if isinstance(i, dict)), {}).items():
            lst = key.split('.')
            obj = task
            for skey in lst[:-1]:
                obj = getattr(obj, skey)

            deflt = getattr(type(obj), lst[-1])
            if value is getattr(self, 'RESET'):
                setattr(obj, lst[-1], deepcopy(deflt))
            else:
                setattr(obj, lst[-1], toenum(deflt, value))

        return task

    def __repr__(self):
        tpe = self.tasktype()
        return (f'<{str(self)}> ↔ {tpe.__module__}.{tpe.__qualname__}\n\n    '
                +'\n    '.join(getattr(_DOCHelper, self.name).value)
                +'\n')

    @classmethod
    @_DOCHelper.add('eventdetection', 'peakselector', 'fittohairpin',
                    header = "The task order consists in:")
    def __taskorder__(cls):
        return cls.eventdetection, cls.peakselector, cls.fittohairpin

    @classmethod
    def __base_cleaning__(cls):
        return cls.subtraction, cls.cleaning, cls.alignment, cls.clipping

    @classmethod
    @_DOCHelper.add('subtraction', 'cleaning', 'alignment', "clipping",
                    header = "Cleaning consists in the following tasks:")
    def __cleaning__(cls):
        return cls.__base_cleaning__()

    @classmethod
    def __tasklist__(cls):
        cleaning = cls.__cleaning__()
        assert cleaning[0] is cls.subtraction
        tasks    = (cls.cyclesampling, cleaning[0], cls.selection) + cleaning[1:]
        ords     = cls.__taskorder__()
        if tasks[-1] == cls.clipping and ords[0] == cls.alignment:
            return tasks[:-1] + ords[:1] + tasks[-1:] + ords[1:]
        return tasks + ords

    @classmethod
    def __nodefault__(cls):
        return cls.cyclesampling, cls.selection, cls.subtraction

    @classmethod
    def _missing_(cls, value) -> 'Tasks':
        drift = cls('driftperbead').tasktype()
        if isinstance(value, Task) and not isinstance(value, drift):
            value = type(value)

        if isinstance(value, type):
            if issubclass(value, drift):
                raise ValueError("DriftTask must be instantiated to be found be Tasks")

            tsk = next((i for i, j in cls.classes().items() if j is value), None)
            if tsk:
                return cls(tsk)

        if isinstance(value, drift):
            return cls('driftper'+('bead' if getattr(value, 'onbeads') else 'cycle'))

        return super()._missing_(value) # type: ignore


    @classmethod
    def __create(cls: Any, arg, kwa): # pylint: disable=too-many-return-statements
        if isinstance(arg, cls):
            return arg(**kwa)

        if isinstance(arg, Track):
            if arg.path is None:
                return InMemoryTrackTask(track = arg)
            arg = arg.path

        if isinstance(arg, Task):
            return update(deepcopy(arg), **kwa)

        if isinstance(arg, type) and issubclass(arg, Task):
            return arg()

        if isinstance(arg, str) and arg in cls.__members__:
            return cls(arg)(**kwa)

        if isinstance(arg, (tuple, list)) and len(arg) >= 1 and callable(arg[0]):
            return cls.action(*arg, **kwa)

        if callable(arg):
            return cls.action(arg)

        if (
                isinstance(arg, (Path, str))
                or (
                    isinstance(arg, (tuple, list))
                    and all(isinstance(i, (Path, str)) for i in arg)
                )
        ):
            info = dict(kwa)
            info.setdefault('path', arg)
            return cls('trackreader').tasktype()(**info)

        if isinstance(arg, (tuple, list)) and len(arg) == 2:
            return cls(arg[0])(**arg[1], **kwa)

        raise RuntimeError(f'Arguments are unexpected: *({arg}), **({kwa})')

@addto(Task)
def nondefaults(self) -> Dict[str, Any]:
    """
    Return non default attributes
    """
    out = eval(taskstore.dumps(self))[1] # pylint: disable=eval-used
    out.pop(taskstore.TPE)
    return out
setattr(Tasks, 'RESET', Ellipsis)
