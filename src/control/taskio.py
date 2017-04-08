#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Task IO module"
from typing         import Union, Tuple
from copy           import deepcopy
from model.task     import TrackReaderTask

class TaskIO:
    u"base class for opening files"
    # pylint: disable=no-self-use,unused-argument
    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        u"opens a file"
        return None

    def save(self, path:str, models):
        u"opens a file"
        return None

    @classmethod
    def __get(cls, ctrl, attr:str):
        ctrl = getattr(ctrl, 'taskcontroller', ctrl)
        return getattr(ctrl, '_TaskController__'+attr)

    @classmethod
    def extensions(cls, ctrl, attr:str):
        "returns the list of possible extensions"
        return '*|'+'|'.join(i.EXT for i in cls.__get(ctrl, attr)[::-1])

    @classmethod
    def insert(cls, ctrl, attr:str, ind, new):
        "returns the list of file openers"
        cls.__get(ctrl, attr).insert(ind, new)

    @classmethod
    def replace(cls, ctrl, attr:str, old, new):
        "returns the list of file openers"
        lst = cls.__get(ctrl, attr)
        ind = lst.index(cls.get(ctrl, attr, old))
        lst[ind] = new

    @classmethod
    def get(cls, ctrl, attr:str, old):
        "returns the list of file openers"
        lst = cls.__get(ctrl, attr)
        if isinstance(old, type):
            # pylint: disable=unidiomatic-typecheck
            return next(j for j in lst if type(j) is old)
        return old

class DefaultTaskIO(TaskIO):
    "will be selected by the taskcontrol by default"

class TrackIO(TaskIO):
    "Deals with reading a track file"
    EXT = 'trk'
    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file"
        if len(model):
            raise NotImplementedError()
        return [(TrackReaderTask(path = path),)]

class ConfigTrackIO(TrackIO):
    "Adds an alignment to the tracks per default"
    EXT = 'trk'
    def __init__(self, ctrl):
        self.__ctrl = ctrl

    @classmethod
    def setup(cls, ctrl, cnf):
        "sets itself-up in stead of TrackIO"
        cls.replace(ctrl, 'openers', TrackIO, cls(cnf))

    def open(self, path:Union[str, Tuple[str,...]], model:tuple):
        "opens a track file and adds a alignment"
        if isinstance(path, str):
            path = path,

        items = [TrackIO().open(path, model)[0][0]]
        for name in self.__ctrl.get(default = tuple()):
            task = self.__ctrl[name].get(default = None)
            if not getattr(task, 'disabled', True):
                items.append(deepcopy(task))
        return [tuple(items)]

class _GrFilesIOMixin:
    "Adds an alignment to the tracks per default"
    def __init__(self):
        self._track = None

    @classmethod
    def setup(cls, ctrl, cnf):
        "sets itself-up just before TrackIO"
        self = cls.get(ctrl, 'openers', cls)
        cnf.observe(lambda itm: setattr(self, '_track', itm.value))

    def _open(self, path:Union[str, Tuple[str,...]], _):
        "opens a track file and adds a alignment"
        if isinstance(path, str):
            path = path,

        if not all(i.endswith('.gr') for i in path):
            return None

        track = self._track
        if track is None:
            raise IOError(u"IOError: start by opening a track file!")

        path = ((track.path,) if isinstance(track.path, str) else track.path) + path
        return type(self).__base__.open(self, path, _) # type: ignore # pylint: disable=no-member

class GrFilesIO(TrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = 'gr'
    def open(self, path:Union[str, Tuple[str,...]], _:tuple):
        return self._open(path, _)

class ConfigGrFilesIO(ConfigTrackIO, _GrFilesIOMixin):
    "Adds an alignment to the tracks per default"
    EXT = 'gr'
    def open(self, path:Union[str, Tuple[str,...]], _:tuple):
        return self._open(path, _)

    @classmethod
    def setup(cls, ctrl, trk, tasks): # pylint: disable=arguments-differ
        self = cls(tasks)
        cls.replace(ctrl, 'openers', GrFilesIO, self)
        trk.observe(lambda itm: setattr(self, '_track', itm.value))
