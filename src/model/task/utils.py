#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Utilitary tasks """
from typing  import List, Callable
from utils   import initdefaults
from ..level import Level
from .base   import Task

class ActionTask(Task):
    "Adds a callable to a frame"
    level          = Level.none
    call: Callable = None

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class ExceptionCatchingTask(Task):
    "Discards beads which throw an exception"
    level                       = Level.none
    exceptions: List[Exception] = []

    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
