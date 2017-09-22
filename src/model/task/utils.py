#!/usr/bin/env python3
# -*- coding: utf-8 -*-
""" Utilitary tasks """
from typing  import List
from utils   import initdefaults
from ..level import Level
from .base   import Task

class ExceptionCatchingTask(Task):
    "Discards beads which throw an exception"
    level                       = Level.none
    exceptions: List[Exception] = []

    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)
        Task.__init__(self, **kwa)
