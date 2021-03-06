#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Generates output from a TaggingTask"
from taskmodel.tagging import TaggingTask
from .base             import Processor


class TaggingProcessor(Processor[TaggingTask]):
    "Generates output from a TaggingTask"
    @classmethod
    def apply(cls, toframe = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        task  = cls.tasktype(**kwa)
        elems = tuple(task.selection)
        if   task.action is cls.tasktype.keep:
            fcn = lambda frame: frame.selecting(elems)

        elif task.action is cls.tasktype.remove:
            fcn = lambda frame: frame.discarding(elems)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**self.config()))
