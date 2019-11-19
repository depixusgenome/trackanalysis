#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating list of jobs to run"
from copy                       import deepcopy
from collections                import OrderedDict
from dataclasses                import dataclass, field
from typing                     import (
    Dict, Union, Iterable, Type, Optional, ItemsView, List, Iterator, Tuple, KeysView, Any
)

import zlib
from   cachetools               import LRUCache
import pandas as pd

from cleaning.beadsubtraction      import FixedBeadDetection
from cleaning.processor.__config__ import FixedBeadDetectionTask
from data.trackio                  import TrackIOError
from taskstore                     import dumps, loads
from taskcontrol.taskcontrol       import ProcessorController
from taskcontrol.processor         import Processor
from taskcontrol.processor.base    import register
from taskmodel.application         import TasksConfig, TasksDisplay
from taskmodel.dataframe           import DataFrameTask
from taskmodel                     import RootTask, Task
from ..processor.__config__        import FitToReferenceTask, FitToHairpinTask

OptProc    = Optional[ProcessorController]
ProcOrRoot = Union[RootTask, ProcessorController]
Cache      = Dict[int, Union[Exception, pd.DataFrame]]
Processors = Dict[RootTask, ProcessorController]
RAW        = False

def keytobytes(tasks: Union[bytes, ProcessorController], raw: bool = RAW) -> bytes:
    "convert to bytes"
    if isinstance(tasks, bytes):
        return tasks
    info = dumps(
        getattr(tasks, 'model', tasks),
        ensure_ascii = False,
        sort_keys    = True,
    ).encode('utf-8')
    return info if raw else zlib.compress(info)

def keyfrombytes(tasks: bytes, raw: bool = RAW) -> List[Task]:
    "convert from bytes"
    return loads((tasks if raw else zlib.decompress(tasks)).decode('utf-8'))


@dataclass
class TaskLRUConfig:
    """info missing from TasksConfig"""
    name:    str                         = "peakcalling.view.lru"
    maxsize: int                         = 5

    def newcache(self) -> '_RootCache':
        "return new cache"
        return _RootCache(self.maxsize)

class TasksDict:
    "Deals with keeping a copy of tasks for each track"
    def __init__(self):
        self.name:  str                        = 'peakcalling.view.tasksdict'
        self.tasks: Processors                 = {}
        self.cache: Dict[RootTask, _RootCache] = {}
        self.lru:   TaskLRUConfig              = TaskLRUConfig()

    def __contains__(self, root: 'ProcOrRoot') -> bool:
        if isinstance(root, ProcessorController) and len(root.model):
            root = root.models[0]

        return root in self.tasks

    def __getitem__(self, root: 'ProcOrRoot') -> 'OptProc':
        if isinstance(root, ProcessorController) and len(root.model):
            root = root.models[0]

        return self.tasks.get(root, None)

    def items(self) -> ItemsView[RootTask, ProcessorController]:
        "return tasks"
        return self.tasks.items()

    def keys(self) -> KeysView[RootTask]:
        "return root tasks"
        return self.tasks.keys()

    def itertask(self, task: Type[Task]) -> Iterator[Tuple[RootTask, Task]]:
        "iterate over tasks selecting the one provide as argument"
        yield from (
            (i.model[0], j)
            for i in self.tasks.values() for j in i.model
            if isinstance(j, task)
        )

    def add(self, procs: ProcessorController):
        "add a processorcontroller"
        self.tasks[procs.model[0]] = self.cleancopy(procs)

    def clear(self, procs: Union[Iterable[ProcessorController], ProcessorController]):
        "clear the lru"
        for i in (procs,) if isinstance(procs, ProcessorController) else procs:
            self.cache[i.model[0]] = self.lru.newcache()

    def swapmodels(self, ctrl):
        "swap models with those in the controller"
        self.lru = ctrl.theme.swapmodels(self.lru)
        self._reset_tasks(ctrl)

    def observe(self, ctrl):
        "updates models as needed"

        def _observe(fcn):

            @ctrl.tasks.observe(fcn.__name__[3:])
            @ctrl.tasks.hashwith(self)
            def _wrapped(**_):
                ctrl.display.handle(
                    self.name,
                    ctrl.display.emitpolicy.outasdict,
                    dict(tasks = self, change = fcn(**_), action = fcn.__name__[3:])
                )

        @_observe
        def _onopentrack(**_) -> dict:
            old = self.tasks
            self._reset_tasks(ctrl)
            return {i: self.tasks[i] for i in  set(self.tasks) - set(old)}

        @_observe
        def _onclosetrack(**_) -> dict:
            old = self.tasks
            self._reset_tasks(ctrl)
            return {i: old[i] for i in  set(old) - set(self.tasks)}

        @_observe
        def _onaddtask(parent, task, **_) -> Tuple[ProcessorController, Task]:
            self.tasks[parent].add(
                task,
                ctrl.tasks.processortype(task),
                ctrl.tasks.processors(parent).model.index(task)
            )
            self.tasks[parent].data.setcachedefault(0, ctrl.tasks.track(parent))
            return self.tasks[parent], task

        @_observe
        def _onupdatetask(parent, task, **_) -> Tuple[ProcessorController, Task]:
            self.tasks[parent].update(task)
            self.tasks[parent].data.setcachedefault(0, ctrl.tasks.track(parent))
            return self.tasks[parent], task

        @_observe
        def _onremovetask(parent, task, **_) -> Tuple[ProcessorController, Task]:
            self.tasks[parent].remove(task)
            self.tasks[parent].data.setcachedefault(0, ctrl.tasks.track(parent))
            return self.tasks[parent], task

    @staticmethod
    def cleancopy(procs: ProcessorController) -> ProcessorController:
        "clean *deeper* copy of the processors"
        new       = ProcessorController(copy = procs.copy)
        new.model = list(procs.model)
        new.data  = procs.data.cleancopy()

        old = procs.data.getcache(0)()
        if old:
            new.data.setcachedefault(0, old)
        return new

    def _reset_tasks(self, ctrl):
        tasks = OrderedDict()
        cache = dict()
        for lst in ctrl.tasks.tasklist(...):
            root = next(lst, None)
            if root is None:
                continue

            if root in self.tasks:
                tasks[root] = self.tasks[root]
                cache[root] = self.cache[root]
            else:
                tasks[root] = self.cleancopy(ctrl.tasks.processors(root))
                cache[root] = self.lru.newcache()

        self.tasks = tasks
        self.cache = cache


_MEASURES: Dict[str, Any] = dict(
    blockageresolution = 'resolution',
    blockagehfsigma    = 'peakhfsigma',
)


@dataclass
class TasksMeasures:
    """info missing from TasksConfig"""
    name:  str           = "peakcalling.view.dataframe"
    peaks: DataFrameTask = field(default_factory = lambda: DataFrameTask(
        measures = dict(**_MEASURES, hfsigma = True)
    ))
    fits:  DataFrameTask = field(default_factory = lambda: DataFrameTask(
        measures = dict(peaks = dict(**_MEASURES, all = True, falseneg = True))
    ))

class TaskState:        # pylint: disable=too-many-instance-attributes
    "Deals with oligos, sequences & reference track"
    def __init__(self):
        self.name:          str                               = 'peakcalling.view.state'
        self.reference:     Optional[RootTask]                = None
        self.seqpath:       Optional[str]                     = None
        self.sequences:     Dict[str, str]                    = {}
        self.probes:        Dict[RootTask, List[str]]         = {}
        self.processors:    Dict[Type[Task], Type[Processor]] = register()
        self.defaultprobes: List[str]                         = ['kmer']
        self.fixed:         FixedBeadDetection                = FixedBeadDetection()

    def swapmodels(self, ctrl):
        "swap models with those in the controller"
        self.reference = ctrl.display.get(
            "hybridstat.fittoreference", "reference", defaultvalue = None
        )
        self.probes     = ctrl.display.get("sequence", "probes",  defaultvalue = {})
        self.seqpath    = ctrl.theme.get("sequence", "path",      defaultvalue = None)
        self.sequences  = ctrl.theme.get("sequence", "sequences", defaultvalue = {})
        self.processors = ctrl.tasks.processortype(...)
        if ctrl.theme.model("fixedbeads") is not None:
            self.fixed  = ctrl.theme.model("fixedbeads")

    def observe(self, ctrl):
        "updates models as needed"

        @ctrl.theme.observe("sequence")
        @ctrl.theme.hashwith(self)
        def _onsequences(model, old, **_):
            itms = {}
            if 'sequences' in old:
                itms['sequences'] = model.sequences
            if 'path' in old:
                itms['seqpath'] = model.path
            if itms:
                ctrl.display.update(self, **itms)

        @ctrl.display.observe("sequence")
        @ctrl.display.hashwith(self)
        def _onprobes(model, old, **_):
            if 'probes' in old:
                ctrl.display.update(self, probes = model.probes)

        @ctrl.display.observe("hybridstat.fittoreference")
        @ctrl.display.hashwith(self)
        def _onreference(model, old, **_):
            if 'reference' in old:
                ctrl.display.update(self, reference = model.reference)

        @ctrl.theme.observe("fixedbeads")
        @ctrl.theme.hashwith(self)
        def _onfixedbeads(model, **_):
            ctrl.display.update(
                self, fixed = FixedBeadDetection(**model.config())
            )

class TasksModel:
    "everything related to tasks"
    tasks:      TasksDict
    state:      TaskState
    config:     TasksConfig
    dataframes: TasksMeasures

    def __init__(self, mdl: Optional['TasksModel'] = None):
        for  i, j in getattr(TasksModel, '__annotations__').items():
            setattr(self, i, getattr(mdl, i) if hasattr(mdl, i) else j())

    def swapmodels(self, ctrl):
        "swap models with those in the controller"
        self.state      = ctrl.display.swapmodels(self.state)
        self.tasks      = ctrl.display.swapmodels(self.tasks)
        self.config     = ctrl.theme.swapmodels(self.config)
        self.dataframes = ctrl.theme.swapmodels(self.dataframes)

        for i in self.__dict__.values():
            if callable(getattr(i, 'swapmodels', None)):
                i.swapmodels(ctrl)

    def observe(self, ctrl):
        "link controller updates to computations"
        self.tasks.observe(ctrl)
        self.state.observe(ctrl)

    @property
    def roots(self) -> Iterator[RootTask]:
        "return root tasks"
        return iter(self.tasks.tasks.keys())

    @property
    def processors(self) -> Processors:
        """return the processors for new jobs"""
        return _Adaptor(self)(False)

    @property
    def missingprocessors(self) -> Dict[RootTask, str]:
        """return the processors for new jobs"""
        return _Adaptor(self)(True)

class _Adaptor:
    "Functor for creating a dictionnary of processors to send to JobRunner"
    tasks:      TasksDict
    state:      TaskState
    config:     TasksConfig
    dataframes: TasksMeasures
    _copies:    Processors

    def __init__(self, mdl: TasksModel):
        self.__dict__.update(mdl.__dict__)

    def __call__(self, withmissing = False) -> Processors:
        self._copies = {i: self.tasks.cleancopy(j) for i, j in self.tasks.items()}

        missing: Dict[RootTask, str] = {}
        initial                      = dict(self._copies)

        self.__fixedbead()
        missing.update({i: "fixed" for i in set(initial) - set(missing) - set(self._copies)})

        self.__fittoreference()
        missing.update({i: "ref" for i in set(initial) - set(missing) - set(self._copies)})

        self.__fittohairpin()
        missing.update({i: "hairpin" for i in set(initial) - set(missing) - set(self._copies)})

        self.__dataframe()
        missing.update({i: "dataframe" for i in set(initial) - set(missing) - set(self._copies)})

        out = self.__dict__.pop('_copies')
        return missing if withmissing else out

    def __add(self, procs, task):
        if task:
            ind = self.config.defaulttaskindex(procs.model, task)
            procs.add(task, self.state.processors[type(task)], ind)

    def __fixedbead(self):
        for procs in self._copies.values():
            self.__add(procs, FixedBeadDetectionTask(**self.state.fixed.config()))

    def __iter(
            self,
            taskname:   str,
            remove:     bool
    ) -> Iterator[Tuple[ProcessorController, int]]:
        tpe = type(self.config.sdi[taskname])
        for root, procs in list(self._copies.items()):
            ind = next(
                (i for i, j in enumerate(procs.model) if isinstance(j, tpe)),
                None
            )
            if remove:
                if ind is not None:
                    procs.remove(ind)
                continue

            if ind is None:
                try:
                    track = TasksDisplay(taskcache = procs).track
                    dflts = getattr(self.config, track.instrument['type'].name)
                except TrackIOError:
                    procs.remove(ind)
                    continue

                task  = deepcopy(dflts[taskname])
            else:
                task  = deepcopy(procs.model[ind])

            task  = yield (procs, task)

            if task is False:
                self._copies.pop(root)

            elif ind is not None:
                procs.remove(ind)

            self.__add(procs, task)

            # This yield is only to return to the enclosing loop, right
            # after the send. The loop will then call the next iteration
            yield  # type: ignore

    def __fittoreference(self):
        ref = self._copies.get(self.state.reference, None)
        itr = self.__iter("fittoreference", ref is None)

        task: FitToReferenceTask
        for procs, task in itr:
            task.defaultdata = ref.data
            itr.send(None if ref is procs else task)

    @staticmethod
    def __resolved(task) -> bool:
        return len(set(task.fit) - {None}) > 0

    def __hasfits(self) -> bool:
        tpe = type(self.config.sdi['fittohairpin'])
        return any(
            self.__resolved(task.resolve(proc.model[0].path))
            for proc in self._copies.values() for task in proc.model
            if isinstance(task, tpe)
        )

    def __fittohairpin(self):
        itr   = self.__iter("fittohairpin", not self.__hasfits())

        task: FitToHairpinTask
        for procs, task in itr:
            # if cannot resolve task: remove
            task = task.resolve(procs.model[0].path)
            itr.send(task if self.__resolved(task) else False)

    def __dataframe(self):
        task  = self.dataframes.fits if self.__hasfits() else self.dataframes.peaks

        for procs in self._copies.values():
            procs.add(task, self.state.processors[type(task)])

            cache = self.tasks.cache.get(procs.model[0], None)
            if cache is None:
                self.tasks.cache[procs.model[0]] = cache = self.tasks.lru.newcache()
            info  = cache.setdefault(procs)
            procs.data.setcache(DataFrameTask, info)
            assert procs.data.getcache(DataFrameTask)() is info

class _RootCache(LRUCache):  # pylint: disable=too-many-ancestors
    "Cache for a given root"
    keytobytes   = staticmethod(keytobytes)
    keyfrombytes = staticmethod(keyfrombytes)

    # pylint: disable=signature-differs
    def __getitem__(self, key: Union[bytes, ProcessorController]) -> Cache:
        return super().__getitem__(self.keytobytes(key))

    def __setitem__(self, key: Union[bytes, ProcessorController], values: Cache):
        super().__setitem__(self.keytobytes(key), values)

    def __delitem__(self, key: Union[bytes, ProcessorController]):
        super().__delitem__(self.keytobytes(key))

    def __contains__(self, key: Union[bytes, ProcessorController]) -> bool:
        return super().__contains__(self.keytobytes(key))

    def setdefault(
            self,
            key:     ProcessorController,
            default: Optional[Cache] = None
    ) -> Cache:
        "return the current cache or a new one if missing"
        bit  = self.keytobytes(key)
        if super().__contains__(bit):
            return super().__getitem__(bit)

        if default is None:
            default = {}
        super().__setitem__(bit, default)
        return default
