#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=wildcard-import,unused-import
"All scripting related to tasks"
from utils.decoration import addto
from .tasks           import Tasks
from .parallel        import parallel

from ..base           import Task, RootTask
from ..level          import Level, PHASE, InstrumentType
from ..order          import TASK_ORDER, taskorder
from ..track          import DataSelectionTask

@addto(DataSelectionTask, staticmethod)
def __scripting_save__() -> bool:
    return False
del addto

locals().update({i.__name__: i for i in Tasks.classes().values()})

__all__ = (['Tasks', 'parallel', 'Task', 'RootTask', 'Level', 'PHASE',
            'InstrumentType'] + list({i.__name__ for i in Tasks.classes().values()}))
