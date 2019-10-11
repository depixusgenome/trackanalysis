#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Deals with global information"
from enum               import Enum
from typing             import (Dict, Optional, List, Iterator, Type,
                                Callable, Any, ClassVar, Iterable, Tuple,
                                TYPE_CHECKING, cast)
from copy               import deepcopy
from utils              import initdefaults
from utils.configobject import ConfigObject
from .base              import Task, RootTask
from .processors        import TaskCacheList
from .dataframe         import DataFrameTask
from .level             import InstrumentType
from .order             import TASK_ORDER, taskorder
from .track             import (CycleSamplingTask, TrackReaderTask,
                                DataSelectionTask, CycleCreatorTask)
if TYPE_CHECKING:
    # pylint: disable=unused-import
    from data.track              import Track                   # noqa
    from taskcontrol.taskcontrol import TaskCacheList     # noqa

Configuration  = Dict[str, Task]
Configurations = Dict[str, Configuration]
Rescalings     = Dict[str, "RescalingParameters"]

class ConfigurationDescriptor:
    """ configurations """
    _Type: ClassVar[Type[Enum]] = InstrumentType
    _instr: str

    def __set_name__(self, _, name):
        self._instr = self._Type(name)

    def __get__(self, inst, owner):
        if inst is None:
            return {i:j for i, j in self._instr.__dict__.items() if i[0] != '_'}
        return inst.__dict__[self._instr.name]

    def __set__(self, inst, val):
        good = dict(val)
        good.update({i: deepcopy(j)
                     for i, j in self.__get__(None, None).items()
                     if i not in good})
        inst.__dict__[self._instr.name] = good
        return good

    @classmethod
    def setupdefaulttask(cls, tasktype: Type[Task], name: str = '', **kwa) -> str:
        "add task to the instruments"
        instruments = {cls._Type(i): kwa.pop(i) for i in set(cls._Type.__members__) & set(kwa)}
        name        = name if name else tasktype.__name__.lower()[:-len('Task')]

        for instr in cls._Type.__members__.values():
            itm = tasktype(**dict(kwa, **instruments.get(instr, {})))
            assert itm == getattr(instr, name, itm)
            setattr(instr, name, itm)
        return name

    @classmethod
    def defaulttaskname(cls, name:str, tasktype: Type[Task]):
        "verify that a task default has been defined"
        name = name if name else tasktype.__name__.lower()[:-len('Task')]
        for i in cls._Type.__members__.values():
            assert isinstance(getattr(i, name, None), tasktype)
        return name

class InstrumentDescriptor:
    """ tasks """
    def __get__(self, inst, owner):
        return (InstrumentType.picotwist.name if inst is None else
                inst.__dict__["instrument"])

    def __set__(self, inst, val):
        inst.__dict__['instrument'] = InstrumentType(val).name
        return inst.__dict__['instrument']

class RescalingParameters:
    "Parameters used for rescaling"
    experimental: float = 1.073      # HP005 sequence length * µm ↔ bases at phase 3 (18 pN)
    mumtobase:    float = 1.e-3      # µm ↔ bases at phase 3 (18 pN)
    sequence:     float = 1073       # HP005 sequence length

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __float__(self) -> float:
        "return the factor to apply to tasks"
        return float(self.experimental/(self.mumtobase*self.sequence))

    def rescale(self, explen, seqlen = None) -> 'RescalingParameters':
        "rescales the current setup"
        return type(self)(
            experimental = explen,
            mumtobase    = self.mumtobase,
            sequence     = self.sequence if seqlen is None else seqlen,
        )

class TasksConfig(ConfigObject, hashattributes = 'name'):
    """
    permanent globals on tasks
    """
    name                      = "tasks"
    instrument: str           = InstrumentType.picotwist.name
    picotwist:  Configuration = cast(Configuration, ConfigurationDescriptor())
    sdi:        Configuration = cast(Configuration, ConfigurationDescriptor())
    muwells:    Configuration = cast(Configuration, ConfigurationDescriptor())
    order:      List[str]     = list(TASK_ORDER)
    rescaling:  Rescalings    = {InstrumentType.muwells.value: RescalingParameters()}

    # make sure all configurations are available
    locals().update({
        i: ConfigurationDescriptor()
        for i in set(InstrumentType.__members__)-set(locals())
    })

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def __getitem__(self, key):
        return getattr(self, InstrumentType(key).name)

    @staticmethod
    def __config__(cmap):
        "simplify a config map"
        for i in {'picotwist', 'sdi', 'muwells'} & set(cmap.maps[0]):
            left            = cmap.maps[1][i]
            cmap.maps[0][i] = {j: k for j, k in cmap.maps[0][i].items() if left[j] != k}

    @property
    def tasks(self) -> Configuration:
        "return the current task list"
        return getattr(self, self.instrument)

    @tasks.setter
    def tasks(self, values):
        "return the current task list"
        return setattr(self, self.instrument, values)

    @property
    def taskorder(self) -> Iterator[Type[Task]]:
        "return the task order"
        return taskorder(self.order)

    def defaulttaskindex(self, tasklist:Iterable[Task], task:Type[Task], side = 0) -> int:
        "returns the default task index"
        if not isinstance(task, type):
            task = type(task)
        order    = tuple(self.taskorder)
        previous = order[:order.index(task)+side]

        curr     = tuple(tasklist)
        for i, tsk in enumerate(curr[1:]):
            if not isinstance(tsk, previous):
                return i+1
        return len(curr)

    def rescale(self, instr, explen, seqlen = None) -> Dict[str, Any]:
        "rescale an instrument according to provided values"
        if None in (instr, explen):
            return {}

        if hasattr(instr, 'experimentallength'):
            # pylint: disable=no-member
            seqlen = getattr(instr, 'sequencelength')[int(explen)]
            explen = getattr(instr, 'experimentallength')[int(explen)]
            instr  = instr.instrument['type']

        assert isinstance(explen, float)
        assert seqlen is None or isinstance(seqlen, float)
        instr = InstrumentType(instr).value

        cnv   = self.rescaling
        if seqlen is None:
            seqlen = cnv[instr].sequence

        old   = float(cnv[instr])
        cnv   = dict(cnv, **{instr: cnv[instr].rescale(explen, seqlen)})
        coeff = float(cnv[instr])/old
        if abs(coeff - 1.) < 1e-5:
            return {}

        return {
            'rescaling': cnv,
            instr: {i: j.rescale(coeff) for i, j in getattr(self, instr).items()}
        }

class TasksDisplay(ConfigObject, hashattributes = 'name'):
    """
    runtime globals on tasks
    """
    name:      str
    taskcache: TaskCacheList
    bead:      Optional[int]

    def __init__(self, **_):
        self.name      = 'tasks'
        self.taskcache = _.get('taskcache', TaskCacheList())
        self.bead      = _.get('bead',      None)

    @property
    def roottask(self) -> Optional[RootTask]:
        "return the first task in the model"
        return None if self.undefined else self.taskcache.model[0]

    @property
    def undefined(self) -> bool:
        "whether the taskcache instance contains anything"
        return not self.taskcache.model

    @property
    def track(self) -> Optional['Track']:
        "return the track associated to the root task"
        if self.undefined:
            return None

        track = self.taskcache.data[0].cache()
        if track is None:
            self.taskcache.run(self.taskcache.model[0])  # create cache if needed
            track = self.taskcache.data[0].cache()
        return track

    @property
    def tasklist(self) -> Iterator[Task]:
        "return the tasklist associated to the root task"
        return iter(() if self.undefined else self.taskcache.model)

    def processors(self, upto:Task = None) -> Optional['TaskCacheList']:
        "return the tasklist associated to the root task"
        return None if self.undefined else self.taskcache.keepupto(upto)

    def cache(self, task) -> Callable[[], Any]:
        "returns the processor's cache if it exists"
        return (
            self.taskcache.data.getcache(task) if task and not self.undefined else
            lambda: None
        )

class TaskIOTheme(ConfigObject, hashattributes  = 'name'):
    """
    Info used when opening track files
    """
    name = "tasks.io"
    tasks:      List[str] = []
    inputs:     List[str] = ['taskstore.control.ConfigAnaIO',
                             'taskcontrol.taskio.ConfigGrFilesIO',
                             'taskcontrol.taskio.ConfigMuWellsFilesIO',
                             'taskcontrol.taskio.ConfigTrackIO']
    outputs:    List[str] = ['taskstore.control.ConfigAnaIO']
    processors: List[str] = []
    clear                 = True
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @property
    def inputtypes(self):
        "return loading objects"
        return [self.__import(itm) for itm in self.inputs]

    @property
    def outputtypes(self):
        "return output objects"
        return [self.__import(itm) for itm in self.outputs]

    @property
    def processortypes(self):
        "return processor objects"
        return [self.__import(itm) for itm in self.processors]

    def setup(self, tasks = None, ioopen = None, iosave = None):
        "creates a new object using the current one and proposed changes"
        cpy = deepcopy(self)
        if tasks is not None:
            cpy.tasks = list(tasks)

        for name, vals in (('inputs', ioopen), ('outputs', iosave)):
            if vals is None:
                continue

            old = getattr(cpy, name)
            new = []
            for i in vals:
                if isinstance(i, (str, int)):
                    new.append(old[i] if isinstance(i, int) else i)
                elif isinstance(i, slice) or i is Ellipsis:
                    new.extend(old if i is Ellipsis else old[i])
            setattr(cpy, name, new)
        return cpy

    @staticmethod
    def __import(name):
        if not isinstance(name, str):
            return name
        modname, clsname = name[:name.rfind('.')], name[name.rfind('.')+1:]
        return getattr(__import__(modname, fromlist = [clsname]), clsname)

class TasksModel:
    "tasks related stuff"
    def __init__(self):
        self.config  = TasksConfig()
        self.display = TasksDisplay()

    def swapmodels(self, ctrl) -> bool:
        """
        adds the current obj to the controller
        """
        old          = self.config
        self.config  = ctrl.theme  .add(self.config, False)
        self.display = ctrl.display.add(self.display, False)
        return old is self.display

    def addto(self, ctrl):
        """
        adds the current obj to the controller
        """
        self.config  = ctrl.theme  .swapmodels(self.config)
        self.display = ctrl.display.swapmodels(self.display)

def rescalingevent(ctrl, params, previous) -> Tuple[bool, Optional[float], Optional[float]]:
    "return the rescaling parameter"
    if 'rescaling' not in params and "taskcache" not in params:
        return True, None, None

    root  = ctrl.display.get("tasks", "roottask")
    if root is None:
        return True, None, None

    model = ctrl.theme.model("tasks")
    instr = getattr(ctrl.tasks.track(root).instrument['type'], 'value', None)
    coeff = float(model.rescaling[instr]) if instr in model.rescaling else 1.
    return (abs(coeff - previous) < 1e-5, coeff, coeff/previous)

def setupdefaulttask(tasktype: Type[Task], name: str = '', **kwa) -> str:
    "add task to the instruments"
    return ConfigurationDescriptor.setupdefaulttask(tasktype, name, **kwa)

def setupio(ctrl, tasks = None, ioopen = None, iosave = None):
    "Set-up things if this view is the main one"
    cnf = ctrl.theme.model("tasks.io", True)
    if cnf is None:
        ctrl.theme.add(TaskIOTheme().setup(tasks, ioopen, iosave), False)
    else:
        diff = cnf.setup(tasks, ioopen, iosave).diff(cnf)
        if diff:
            ctrl.theme.updatedefaults(cnf, **diff)


setupdefaulttask(CycleSamplingTask)
setupdefaulttask(TrackReaderTask)
setupdefaulttask(DataSelectionTask)
setupdefaulttask(CycleCreatorTask)
setupdefaulttask(DataFrameTask)
