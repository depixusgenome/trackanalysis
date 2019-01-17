#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Task for creating dataframes

**Warning** Those definitions must remain data-independant.
"""
from   typing import Sequence, Dict, Union, List, Callable, Optional

from   utils  import initdefaults
from   .level import Level
from   .base  import Task

class DataFrameTask(Task):
    """
    Transform a `TrackView` to one or more `pandas.DataFrame`.

    # Attributes

    * `merge`: whether to return one dataframe per element or a single one per view.
    * `indexes`: the columns to use as indexes. This list may be over-complete
    depending on the level the task is applied to.
    * `measures`: the name of a column and the function for creating its values.
    * `transform`: actions to be performed on the finalized dataframe.
    """
    level                                      = Level.none
    merge                                      = False
    indexes:   Sequence[str]                   = ['track', 'bead', 'cycle', 'event']
    measures:  Dict[str, Union[bool, Callable, str]] = {}
    transform: Optional[List[Callable]]              = None
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)
