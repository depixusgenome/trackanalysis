#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=wildcard-import
"All scripting related to tasks"
from .tasks                   import Tasks
from .parallel                import parallel

from ..task                   import Task, RootTask
from ..task.order             import TASK_ORDER, taskorder
locals().update(Tasks.defaults())
