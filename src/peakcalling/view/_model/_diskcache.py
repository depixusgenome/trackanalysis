#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Save the task data to the disk"
from dataclasses          import dataclass
from pathlib              import Path
from pickle               import UnpicklingError
from shutil               import rmtree
from typing               import Iterable, List, Optional, ClassVar, Union
from diskcache            import Cache as DiskCache
from taskmodel.processors import TaskCacheList
from taskmodel.dataframe  import DataFrameTask
from ._jobs               import JobEventNames
from ._tasks              import keytobytes


@dataclass(unsafe_hash = True)
class DiskCacheConfig:
    "The disk cache configuration"
    name:     str = 'peakcalling.diskcache'
    path:     str = ""
    maxsize:  int = int(100e6)
    eviction: str = 'least-frequently-used'
    duration: int = 86400*30

    def newcache(self, cache: Optional[DiskCache] = None) -> DiskCache:
        "create new cache"
        if isinstance(cache, DiskCache):
            return cache
        return DiskCache(
            directory       = self.path,
            min_file_size   = 0,
            size_limit      = self.maxsize,
            eviction_policy = self.eviction
        )

    def insert(
            self,
            items:   Union[Iterable[TaskCacheList], TaskCacheList],
            version: int,
            cache:   Optional[DiskCache] = None
    ):
        """
        add items to the disk
        """
        if self.maxsize == 0:
            return

        with self.newcache(cache) as disk:
            for itm in (items,) if isinstance(items, TaskCacheList) else items:
                key  = keytobytes(itm.model)
                cur  = disk.get(key, tag = True)
                if cur[0] is None or cur[1] != version:
                    data = itm.data.getcache(DataFrameTask)()
                    disk.set(key, data, tag = version, expire = self.duration)

    def get(
            self,
            itm:     TaskCacheList,
            version: int,
            cache:   Optional[DiskCache] = None
    ):
        """
        gets the items from the disk
        """
        if self.maxsize == 0:
            return None

        key = keytobytes(itm.model)
        with self.newcache(cache) as disk:
            try:
                cur, tag  = disk.get(key, tag = True)
                if tag == version:
                    return cur
            except UnpicklingError:
                pass

        return None

    def update(
            self,
            items:   Union[Iterable[TaskCacheList], TaskCacheList],
            version: int,
            cache:   Optional[DiskCache] = None
    ):
        """
        gets the items from the disk
        """
        if self.maxsize == 0:
            return

        with self.newcache(cache) as disk:
            for itm in (items,) if isinstance(items, TaskCacheList) else items:
                data = itm.data.getcache(DataFrameTask)()
                cur  = self.get(itm, version, disk) if isinstance(data, dict) else None
                if isinstance(cur, dict):
                    data.update(cur)

    def clear(
            self,
            complete:   Optional[bool]                = None,
            processors: Optional[List[TaskCacheList]] = None
    ):
        "clear the disk cache"

        if not Path(self.path).exists():
            return

        if complete is None and processors is None:
            complete = self.maxsize <= 0

        if complete:
            rmtree(self.path, ignore_errors = True)
        elif processors is not None:
            with self.newcache() as cache:
                for i in processors:
                    try:
                        del cache[keytobytes(i)]
                    except KeyError:
                        pass
        else:
            with self.newcache() as cache:
                cache.expire()
                cache.cull()

class DiskCacheController:
    "disck cache controller"
    _PREFIX: ClassVar[str] = "cache"

    def __init__(self, events: Optional[JobEventNames] = None):
        self.config = DiskCacheConfig()
        self.events = JobEventNames(events)

    def swapmodels(self, ctrl):
        "swap models with those in the controller"
        if not self.config.path:
            self.config.path = str(ctrl.apppath()/self._PREFIX)
        self.config      = ctrl.theme.swapmodels(self.config)
        self.events      = ctrl.display.swapmodels(self.events)

    def observe(self, ctrl):
        "adds observers to the controller"
        strvers: str = ctrl.version()
        if '_v' in strvers:
            strvers = strvers[strvers.rfind('_v')+2:]

        if '-' in strvers:
            strvers = strvers[:strvers.find('-')]

        version = sum(int(i if i else 0)*j for i, j in zip(strvers.split('.'), (1000, 1)))

        @ctrl.display.observe("applicationstarted", "applicationstopped")
        @ctrl.display.hashwith(self.config)
        def _onapplicationstarted(**_):
            self.config.clear()

        @ctrl.display.observe(self.events.eventjobstart)
        @ctrl.display.hashwith(self.config)
        def _onstartjob(processors: List[TaskCacheList], **_):
            self.config.update(processors, version)

        @ctrl.display.observe(self.events.eventjobstop)
        @ctrl.display.hashwith(self.config)
        def _onstopjob(processors: List[TaskCacheList], **_):
            self.config.insert(processors, version)

        @ctrl.theme.observe(self.config)
        @ctrl.theme.hashwith(self.config)
        def _onconfig(old, **_):
            if self.config.maxsize < old.get('maxsize', 0):
                self.config.clear()
