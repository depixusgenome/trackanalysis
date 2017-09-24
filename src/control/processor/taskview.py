#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Makes TaskView Dicts easier"
from typing     import Generic, TypeVar
from functools  import partial

from data.views import TaskView
from model.task import Task
from .base      import Processor

TaskType = TypeVar('TaskType', bound = Task)
TaskDict = TypeVar('TaskDict', bound = TaskView)
Key      = TypeVar('Key')

class TaskViewProcessor(Generic[TaskType, TaskDict, Key], Processor[TaskType]):
    "Groups beads per hairpin"
    @classmethod
    def taskdicttype(cls) -> type:
        "returns the taskdicttype"
        return cls.__orig_bases__[0].__args__[1] # type: ignore

    @classmethod
    def apply(cls, toframe = None, **cnf):
        "applies the task to a frame or returns a function that does so"
        if toframe is None:
            return partial(cls.apply, **cnf)
        return toframe.new(cls.taskdicttype(), config = cnf)

    @classmethod
    def compute(cls, key: Key, **kwa):
        "Action applied to the frame"
        out = cls.taskdicttype()(config = kwa).compute(key)
        return out.key, out

    def run(self, args):
        "updates the frames"
        args.apply(self.apply(**self.config()))
