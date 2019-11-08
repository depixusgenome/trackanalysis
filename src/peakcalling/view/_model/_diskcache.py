#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Save the task data to the disk"
import time
from dataclasses          import dataclass
from pathlib              import Path
from pickle               import UnpicklingError
from shutil               import rmtree
from typing               import Iterable, List, Optional, ClassVar, Union
from diskcache            import Cache as DiskCache
import version as _version
from data.trackops        import trackname
from taskmodel.processors import TaskCacheList
from taskmodel.dataframe  import DataFrameTask
from ...processor         import FitToHairpinTask
from ._jobs               import JobEventNames
from ._tasks              import keytobytes, keyfrombytes

# database version
# WARNING: changing this number will have cycleapp delete the current database
# One should setup a database updater for each version
VERSION     = 1
VERSION_KEY = b"VERSION"

def appversion() -> int:
    "app version"
    strvers: str = _version.version()
    if '_v' in strvers:
        strvers = strvers[strvers.rfind('_v')+2:]

    if '-' in strvers:
        strvers = strvers[:strvers.find('-')]
    strvers = strvers.replace('+', '')

    return sum(int(i if i else 0)*j for i, j in zip(strvers.split('.'), (1000, 1)))


APPVERSION: int   = appversion()
PREFIX:     bytes = b'data_'


@dataclass(unsafe_hash = True)
class DiskCacheConfig:
    "The disk cache configuration"
    name:     str   = 'peakcalling.diskcache'
    path:     str   = ""
    maxsize:  int   = int(100e6)
    eviction: str   = 'least-frequently-used'
    duration: int   = 86400*30

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
            version: int                 = APPVERSION,
            cache:   Optional[DiskCache] = None
    ):
        """
        add items to the disk
        """
        if self.maxsize == 0:
            return

        with self.newcache(cache) as disk:
            if disk.get(VERSION_KEY) != VERSION:
                return

            for itm in (items,) if isinstance(items, TaskCacheList) else items:
                key  = keytobytes(itm.model)
                cur  = disk.get(key, tag = True)
                if cur[0] is None or cur[1] != version:
                    track = itm.data.getcache(0)()
                    data  = itm.data.getcache(DataFrameTask)()
                    disk.set(key, data, tag = version, expire = self.duration)
                    disk.set(
                        PREFIX+key,
                        f"""
                        statsdate = {time.time()}
                        trackdate = {track.pathinfo.modification.timestamp() if track else 0}
                        fit       = {any(isinstance(i, FitToHairpinTask) for i in itm.model)}
                        title     = {trackname(itm.model[0])}
                        path      = {track.pathinfo.trackpath if track else itm.model[0].path}
                        """,
                        tag     = version,
                        expire  = self.duration
                    )

    def iterkeys(
            self,
            version: int                 = APPVERSION,
            cache:   Optional[DiskCache] = None,
            parse:   bool                = False
    ):
        'iterate through keys'
        if self.maxsize == 0:
            return

        def _parse(key, val):
            info = dict(
                {
                    j[:j.find('=')].strip(): j[j.find('=')+1:].strip()
                    for j in val.split('\n')
                },
                model = keyfrombytes(key[len(PREFIX):])
            )
            info['statsdate'] = float(info['statsdate'])
            info['trackdate'] = float(info['trackdate'])
            info['fit']       = info['fit'] == 'True'
            return info

        fcn = _parse if parse else lambda _, val: val

        with self.newcache(cache) as disk:
            if disk.get(VERSION_KEY) == VERSION:
                for i in disk.iterkeys():
                    if i.startswith(PREFIX):
                        cur, tag = disk.get(i, tag = version)
                        if tag == version:
                            yield (i[len(PREFIX):], fcn(i, cur))

    def get(
            self,
            itm:     TaskCacheList,
            version: int                 = APPVERSION,
            cache:   Optional[DiskCache] = None
    ):
        """
        gets the items from the disk
        """
        if self.maxsize == 0:
            return None

        with self.newcache(cache) as disk:
            key = keytobytes(itm.model)
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
            version: int                 = APPVERSION,
            cache:   Optional[DiskCache] = None
    ):
        """
        gets the items from the disk
        """
        if self.maxsize == 0:
            return

        with self.newcache(cache) as disk:
            if disk.get(VERSION_KEY) != VERSION:
                return

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
        if complete is None and processors is None and self.maxsize <= 0:
            complete = True

        if Path(self.path).exists() and not complete:
            if processors is None:
                processors = []

            with self.newcache() as cache:
                complete = complete or cache.get(VERSION_KEY, 0) < VERSION
                if not complete:
                    for i in processors:
                        key = keytobytes(i)
                        try:
                            del cache[key]
                            del cache[PREFIX+key]
                        except KeyError:
                            pass

                    cache.expire()
                    cache.cull()

        if complete:
            rmtree(self.path, ignore_errors = True)

        if self.maxsize > 0 and not Path(self.path).exists():
            with self.newcache() as cache:
                cache.set(VERSION_KEY, VERSION)

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

    def iterkeys(self, parse: bool = False):
        "iterate through keys"
        yield from self.config.iterkeys(parse = parse)

    def observe(self, ctrl):
        "adds observers to the controller"
        @ctrl.display.observe("applicationstarted", "applicationstopped")
        @ctrl.display.hashwith(self.config)
        def _onapplicationstarted(**_):
            self.config.clear()

        @ctrl.display.observe(self.events.eventjobstart)
        @ctrl.display.hashwith(self.config)
        def _onstartjob(processors: List[TaskCacheList], **_):
            self.config.update(processors)

        @ctrl.display.observe(self.events.eventjobstop)
        @ctrl.display.hashwith(self.config)
        def _onstopjob(processors: List[TaskCacheList], **_):
            self.config.insert(processors)

        @ctrl.theme.observe(self.config)
        @ctrl.theme.hashwith(self.config)
        def _onconfig(old, **_):
            if self.config.maxsize < old.get('maxsize', 0):
                self.config.clear()
