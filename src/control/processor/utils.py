#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Utilitary tasks """
from typing           import Tuple, Type
from functools        import partial
from model.task.utils import ExceptionCatchingTask
from .base            import Processor

class ExceptionCatchingProcessor(Processor):
    "Discards beads which throw an exception"
    tasktype = ExceptionCatchingTask
    @staticmethod
    def __test(exc: Tuple[Type[Exception],...], frame):
        if not exc:
            return []
        bad = []
        for i in frame.data.keys():
            try:
                frame.data[i]
            except Exception as this: # pylint: disable=broad-except
                if isinstance(this, exc):
                    bad.append(i)
                else:
                    raise
        return bad

    @classmethod
    def apply(cls, toframe = None, exceptions = None, **_):
        "applies the task to a frame or returns a method that will"
        exc = tuple(exceptions) if exceptions else ()
        return toframe.new().discarding(partial(cls.__test, exc))

    def run(self, args):
        "updates the frames"
        return args.apply(partial(self.apply, exceptions = self.task.exceptions))
