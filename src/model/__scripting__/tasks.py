#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkeypatches tasks and provides a simpler access to usual tasks
"""
from pathlib                  import Path
from functools                import partial
from typing                   import Type, Tuple, List, Callable, Dict, Any, cast
from concurrent.futures       import ProcessPoolExecutor

from copy                     import deepcopy
from enum                     import Enum

import anastore
from utils                    import update
from utils.decoration         import addto
from utils.attrdefaults       import toenum
from data.views               import TrackView
from control.taskcontrol      import create as _create, ProcessorController
from control.processor.base   import Processor, register
from control.processor.utils  import ActionTask
from cleaning.processor       import DataCleaningTask
from cleaning.beadsubtraction import BeadSubtractionTask
from cordrift.processor       import DriftTask
from eventdetection.processor import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor    import (PeakSelectorTask, PeakCorrelationAlignmentTask,
                                      SingleStrandTask)
from peakcalling.processor    import (FitToReferenceTask, FitToHairpinTask,
                                      BeadsByHairpinTask)
from ..level                  import Level
from ..task                   import (Task, TrackReaderTask, CycleCreatorTask,
                                      DataSelectionTask)
from ..task.track             import CycleSamplingTask
from ..task.dataframe         import DataFrameTask

class _DOCHelper(Enum):
    # pylint: disable=bad-continuation
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
    cyclesampling  = 'cyclesampling'
    action         = 'action'
    subtraction    = 'subtraction'
    cleaning       = 'cleaning'
    selection      = 'selection'
    alignment      = 'alignment'
    driftperbead   = 'driftperbead'
    driftpercycle  = 'driftpercycle'
    cycles         = 'cycles'
    eventdetection = 'eventdetection'
    peakalignment  = 'peakalignment'
    peakselector   = 'peakselector'
    singlestrand   = 'singlestrand'
    fittohairpin   = 'fittohairpin'
    fittoreference = 'fittoreference'
    beadsbyhairpin = 'beadsbyhairpin'
    dataframe      = 'dataframe'

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
        return cls.subtraction, cls.cleaning, cls.alignment

    @classmethod
    @_DOCHelper.add('subtraction', 'cleaning', 'alignment',
                    header = "Cleaning consists in the following tasks:")
    def __cleaning__(cls):
        return cls.__base_cleaning__()

    @classmethod
    def __tasklist__(cls):
        cleaning = cls.__cleaning__()
        assert cleaning[0] is cls.subtraction
        return (cls.cyclesampling, cleaning[0], cls.selection) + cleaning[1:] + cls.__taskorder__()

    @classmethod
    def __nodefault__(cls):
        return cls.cyclesampling, cls.selection, cls.subtraction

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, Task) and not isinstance(value, DriftTask):
            value = type(value)

        if isinstance(value, type):
            if issubclass(value, DriftTask):
                raise ValueError("DriftTask must be instantiated to be found be Tasks")

            tsk = next((i for i, j in cls.defaults().items() if j.__class__ is value), None)
            if tsk:
                return cls(tsk)

        if isinstance(value, DriftTask):
            return (Tasks.driftperbead if cast(DriftTask, value).onbeads else
                    Tasks.driftpercycle)

        super()._missing_(value) # type: ignore

    @staticmethod
    def defaults():
        "returns default tasks"
        return dict(cleaning       = DataCleaningTask(),
                    cyclesampling  = CycleSamplingTask(),
                    subtraction    = BeadSubtractionTask(),
                    selection      = DataSelectionTask(),
                    alignment      = ExtremumAlignmentTask(),
                    driftperbead   = DriftTask(onbeads = True),
                    driftpercycle  = DriftTask(onbeads = False),
                    cycles         = CycleCreatorTask(),
                    eventdetection = EventDetectionTask(),
                    peakalignment  = PeakCorrelationAlignmentTask(),
                    peakselector   = PeakSelectorTask(),
                    singlestrand   = SingleStrandTask(),
                    fittoreference = FitToReferenceTask(),
                    fittohairpin   = FitToHairpinTask(),
                    beadsbyhairpin = BeadsByHairpinTask(),
                    dataframe      = DataFrameTask())

    def default(self) -> Task:
        "returns default tasks"
        return self.defaults()[self.name]

    def tasktype(self) -> Type[Task]:
        "returns the task type"
        return type(self.default())

    @classmethod
    def create(cls, *args, beadsonly = True, **kwa):
        "returns the task associated to the argument"
        if len(args) == 1:
            return cls.__create(args[0], kwa, beadsonly)
        return [cls.__create(i, kwa, beadsonly) for i in args]

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
            mdl = anastore.load(tasks[0])
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
    def processors(cls, *args, copy = True, beadsonly = True) -> ProcessorController:
        "Return a `ProcessorController` containing selected tasks."
        procs      = _create(*cls.tasklist(*args, beadsonly = beadsonly))
        procs.copy = copy
        return procs

    @classmethod
    @_DOCHelper.add(header = "These can be:")
    def apply(cls, *args, copy = True, beadsonly = True, pool = None) -> TrackView:
        "Return an iterator over the result of selected tasks."
        procs = cls.processors(*args, beadsonly = beadsonly)
        ret   = isinstance(pool, bool)
        if ret:
            pool = ProcessPoolExecutor()

        out = next(iter(procs.run(copy = copy, pool = pool)))
        if ret:
            with pool:
                out = tuple(out)
        return out

    def dumps(self, **kwa):
        "returns the json configuration"
        kwa.setdefault('saveall', False)
        kwa.setdefault('indent', 4)
        kwa.setdefault('ensure_ascii', False)
        kwa.setdefault('sort_keys', True)
        kwa.setdefault('patch', None)
        return anastore.dumps(self, **kwa)

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

    def processor(self, *resets, **kwa) -> Processor:
        "Returns the default processor for this task"
        task  = self(*resets, **kwa)
        return register(None)[type(task)](task = task)

    def __call__(self, *resets, **kwa)-> Task:
        fcn     = getattr(self, '_default_'+self.name, None)
        if fcn is not None:
            return fcn(*resets, **kwa)

        current = kwa.pop('current', None)
        cnf     = self.default() if current is None else deepcopy(current)
        cls     = type(cnf)
        if Ellipsis in resets:
            resets = tuple(i for i in resets if i is not Ellipsis)

        kwa.update({i: getattr(cls, i) for i in resets if isinstance(i, str)})

        state = cnf.__getstate__() if hasattr(cnf, '__getstate__') else deepcopy(cnf.__dict__)
        state.update(**kwa)
        task  = cnf.__class__(**state)

        for key, value in next((i for i in resets if isinstance(i, dict)), {}).items():
            lst = key.split('.')
            obj = task
            for skey in lst[:-1]:
                obj = getattr(obj, skey)

            deflt = getattr(type(obj), lst[-1])
            if value is self.RESET:
                setattr(obj, lst[-1], deepcopy(deflt))
            else:
                setattr(obj, lst[-1], toenum(deflt, value))

        return task

    class _TaskGetter:
        def __get__(self, obj, tpe):
            return tpe.create if obj is None else obj

    get = _TaskGetter()

    @classmethod
    def __create(cls, arg, kwa, beadsonly): # pylint: disable=too-many-return-statements
        if isinstance(arg, cls):
            return arg(**kwa)

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

        if (isinstance(arg, (Path, str))
                or (isinstance(arg, (tuple, list))
                    and isinstance(i, (Path, str)) for i in arg)):
            info = dict(kwa)
            info.setdefault('path', arg)
            info.setdefault('beadsonly', beadsonly)
            return TrackReaderTask(**info)

        if isinstance(arg, (tuple, list)) and len(arg) == 2:
            return cls(arg[0])(**arg[1], **kwa)

        raise RuntimeError('arguments are unexpected')

@addto(Task)
def nondefaults(self) -> Dict[str, Any]:
    """
    Return non default attributes
    """
    out = eval(anastore.dumps(self))[1] # pylint: disable=eval-used
    out.pop(anastore.TPE)
    return out

setattr(Tasks, 'RESET', Ellipsis)
