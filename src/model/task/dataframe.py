#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task for creating dataframes

**Warning** Those definitions must remain data-independant.
"""
from   typing   import Sequence, Dict, Union, Callable

from   utils    import initdefaults
from   ..level  import Level
from   .base    import Task

class DataFrameTask(Task):
    "Task for creating dataframes"
    level                                     = Level.none
    merge                                     = False
    indexes: Sequence[str]                    = ['track', 'bead', 'cycle', 'event']
    measures: Dict[str, Union[Callable, str]] = {}
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
