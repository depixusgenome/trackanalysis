#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Utilitary tasks """
from typing           import Tuple, Type
from functools        import partial
from model.task.utils import ExceptionCatchingTask, ActionTask
from .base            import Processor

class ActionProcessor(Processor[ActionTask]):
    "Adds a callable to a frame"
    @classmethod
    def apply(cls, toframe, call = None, **_):
        "applies the task to a frame or returns a method that will"
        return toframe.withaction(call) if call else toframe

    def run(self, args):
        "updates the frames"
        return args.apply(partial(self.apply, call = self.task.call))

class ExceptionCatchingProcessor(Processor[ExceptionCatchingTask]):
    "Discards beads which throw an exception"
    @staticmethod
    def _test(exc: Tuple[Type[Exception],...], frame):
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
        return toframe.new().discarding(partial(cls._test, exc))

    def run(self, args):
        "updates the frames"
        return args.apply(partial(self.apply, exceptions = self.task.exceptions))
