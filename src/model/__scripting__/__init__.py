#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=wildcard-import
"All scripting related to tasks"
from utils.decoration import addto
from .tasks           import Tasks
from .parallel        import parallel

from ..task           import Task, RootTask
from ..task.order     import TASK_ORDER, taskorder
from ..task.track     import DataSelectionTask
from ..globals        import LocalContext

@addto(DataSelectionTask, staticmethod)
def __scripting_save__() -> bool:
    return False
del addto

locals().update({type(i).__name__: type(i) for i in Tasks.defaults().values()})

__all__ = (['LocalContext', 'Tasks', 'parallel', 'Task', 'RootTask']
           + list({type(i).__name__ for i in Tasks.defaults().values()}))
