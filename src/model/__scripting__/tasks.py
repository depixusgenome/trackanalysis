#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monkeypatches tasks and provides a simpler access to usual tasks
"""
from pathlib                  import Path
from functools                import partial
from typing                   import Type, Tuple, List, cast

from copy                     import deepcopy
from enum                     import Enum

import anastore
from utils                    import update
from utils.attrdefaults       import toenum
from control.taskcontrol      import create as _create
from control.processor.utils  import ActionTask
from cleaning.processor       import DataCleaningTask
from cordrift.processor       import DriftTask
from eventdetection.processor import ExtremumAlignmentTask, EventDetectionTask
from peakfinding.processor    import PeakSelectorTask, PeakCorrelationAlignmentTask
from peakcalling.processor    import (FitToReferenceTask, FitToHairpinTask,
                                      BeadsByHairpinTask)
from ..level                  import Level
from ..task                   import (Task, TrackReaderTask, CycleCreatorTask,
                                      DataSelectionTask)
from ..task.dataframe         import DataFrameTask

class Tasks(Enum):
    """
    Possible tasks

    These can be created as follows:

        >>> task = Tasks.alignment()
        >>> assert isinstance(task, ExtremumAlignmentTask)

    Attribute values can be set:

        >>> assert Tasks.peakselector().align is not None         # default value
        >>> assert Tasks.peakselector(align = None).align is None # change default
        >>> assert Tasks.peakselector('align').align is not None  # back to true default

    or:

        >>> assert Tasks.peakselector(align = None).align is None # change default
        >>> assert Tasks.peakselector(align = Tasks.RESET).align is not None  # back to true default

    It's also possible to set sub-fields:
        >>> assert Tasks.peakselector().group.mincount == 5
        >>> assert Tasks.peakselector({'group.mincount': 2}).group.mincount == 2
        >>> assert Tasks.peakselector({'group.mincount': 2}).group.mincount == 2

    For example, to create aligned events and change their stretch and bias:

        >>> def fcn(stretch, bias, info):
        ...     info['data'][:] = [(i-bias)*stretch for i in info['data']]
        >>> Tasks.apply("my path to data",
        ...             Tasks.alignment, Tasks.eventdetection,
        ...             lambda i: fcn(2., .5, i),
        ...             Tasks.peakalignment)

    or:

        >>> Tasks.apply("my path to data",
        ...             Tasks.alignment, Tasks.eventdetection,
        ...             Task.action(fcn, 2., .5),
        ...             Tasks.peakalignment)
    """
    action         = 'action'
    cleaning       = 'cleaning'
    selection      = 'selection'
    alignment      = 'alignment'
    driftperbead   = 'driftperbead'
    driftpercycle  = 'driftpercycle'
    cycles         = 'cycles'
    eventdetection = 'eventdetection'
    peakalignment  = 'peakalignment'
    peakselector   = 'peakselector'
    fittohairpin   = 'fittohairpin'
    fittoreference = 'fittoreference'
    beadsbyhairpin = 'beadsbyhairpin'
    dataframe      = 'dataframe'
    RESET          = Ellipsis

    __taskorder__  = 'eventdetection', 'peakselector', 'fittohairpin'
    __cleaning__   = 'cleaning', 'alignment'
    __tasklist__   = __cleaning__ + __taskorder__

    @staticmethod
    def defaults():
        "returns default tasks"
        return dict(cleaning       = DataCleaningTask(),
                    selection      = DataSelectionTask(),
                    alignment      = ExtremumAlignmentTask(),
                    driftperbead   = DriftTask(onbeads = True),
                    driftpercycle  = DriftTask(onbeads = False),
                    cycles         = CycleCreatorTask(),
                    eventdetection = EventDetectionTask(),
                    peakalignment  = PeakCorrelationAlignmentTask(),
                    peakselector   = PeakSelectorTask(),
                    fittoreference = FitToReferenceTask(),
                    fittohairpin   = FitToHairpinTask(),
                    beadsbyhairpin = BeadsByHairpinTask(),
                    dataframe      = DataFrameTask())

    def default(self):
        "returns default tasks"
        return self.defaults()[self.value]

    @classmethod
    def create(cls, *args, beadsonly = True, **kwa):
        "returns the task associated to the argument"
        if len(args) == 1:
            return cls.__create(args[0], kwa, beadsonly)
        return [cls.__create(i, kwa, beadsonly) for i in args]

    @classmethod
    def defaulttaskorder(cls, order = None) -> Tuple[Type[Task],...]:
        "returns the default task order"
        if order is None:
            order =  cls.__taskorder__
        items = tuple(type(cls(i)()) for i in order[::-1])
        return cast(Tuple[Type[Task],...], items[::-1])

    @classmethod
    def defaulttasklist(cls, paths, upto, cleaned:bool) -> List[Task]:
        "Returns a default task list depending on the type of raw data"
        tasks = list(cls.__tasklist__) # type: ignore
        if cleaned or (isinstance(paths, (tuple, list)) and len(paths) > 1):
            tasks = [i for i in tasks if i not in cls.__cleaning__] # type: ignore

        upto = getattr(upto, 'value', upto)
        itms = (tasks if upto is None       else
                ()    if upto not in tasks  else
                tasks[:tasks.index(upto)+1])
        return [cls(i) for i in itms] # type: ignore

    @classmethod
    def tasklist(cls, *tasks, **kwa) -> List[Task]:
        "Same as create except that a list may be completed as necessary"
        tmp    = cls.get(*tasks, **kwa)
        lst    = cast(List[Task], [tmp] if isinstance(tmp, Task) else tmp)

        torder = cls.defaulttaskorder()[::-1]
        for i, itm in enumerate(torder[:-1]):
            ind = next((i for i, j in enumerate(lst) if isinstance(j, itm)), None)
            if ind is None:
                continue

            ival = ind
            while ival > 0 and getattr(lst[ival-1], 'level', None) is Level.none:
                ival -= 1
            if ival == 0 or not isinstance(lst[ival-1], torder[i+1]):
                name = torder[i+1].__name__.lower().replace('task', '')
                lst.insert(ind, cls.get(name, **kwa))
        return lst

    @classmethod
    def processors(cls, *args, copy = True, beadsonly = True):
        "returns an iterator over the result of provided tasks"
        procs      = _create(cls.tasklist(*args, beadsonly = beadsonly))
        procs.copy = copy
        return procs

    @classmethod
    def apply(cls, *args, copy = True, beadsonly = True):
        "returns an iterator over the result of provided tasks"
        return next(iter(cls.processors(*args, beadsonly = beadsonly).run(copy = copy)))

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

    def __call__(self, *resets, **kwa)-> Task:
        fcn     = getattr(self, '_default_'+self.value, None)
        if fcn is not None:
            return fcn(*resets, **kwa)

        current = kwa.pop('current', None)
        cnf     = self.default() if current is None else deepcopy(current)
        cls     = type(cnf)
        if Ellipsis in resets:
            resets = tuple(i for i in resets if i is not Ellipsis)


        kwa.update({i: getattr(cls, i) for i, j in kwa.items() if j is self.RESET})
        kwa.update({i: getattr(cls, i) for i in resets if isinstance(i, str)})
        task = update(deepcopy(cnf), **kwa)

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

        return getattr(task, '__scripting__', lambda x: task)(kwa)

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
