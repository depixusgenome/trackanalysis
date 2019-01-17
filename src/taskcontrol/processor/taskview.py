#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Makes TaskView Dicts easier"
from typing             import Generic, TypeVar, Dict, Any
from functools          import partial

from utils.inspection   import templateattribute
from data.views         import TaskView
from taskmodel          import Task
from .base              import Processor


TaskType = TypeVar('TaskType', bound = Task)
TaskDict = TypeVar('TaskDict', bound = TaskView)
Key      = TypeVar('Key')

class TaskViewProcessor(Generic[TaskType, TaskDict, Key], Processor[TaskType]):
    "Groups beads per hairpin"
    @staticmethod
    def createcache(_):
        "returns a new cache"
        return False

    @classmethod
    def taskdicttype(cls) -> type:
        "returns the taskdicttype"
        return templateattribute(cls, 1)

    @staticmethod
    def keywords(cnf:Dict[str, Any]) -> Dict[str, Any]:
        "changes keywords as needed"
        return cnf

    @classmethod
    def apply(cls, toframe = None, cache = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        cnf = cls.keywords(cnf)
        if toframe is None:
            if cache is None:
                return partial(cls.apply, **cnf)
            return partial(cls.apply, cache = cache, **cnf)

        if cache is None:
            return toframe.new(cls.taskdicttype(), config = cnf)
        return toframe.new(cls.taskdicttype(), config = cnf, cache = cache)

    @classmethod
    def compute(cls, key: Key, **kwa):
        "Action applied to the frame"
        out = cls.taskdicttype()(config = kwa).compute(key)
        return out.key, out

    def run(self, args):
        "updates the frames"
        cache = self.createcache(args)
        cnf   = self.config()
        if cache is not False:
            cnf['cache'] = cache

        args.apply(self.apply(**cnf))
