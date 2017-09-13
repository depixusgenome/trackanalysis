#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classes defining a type of data treatment.

**Warning** Those definitions must remain data-independant.
"""
from .base  import Task, RootTask, DataFunctorTask, TaskIsUniqueError, Level
from .track import TrackReaderTask, CycleCreatorTask, DataSelectionTask
from .order import TASK_ORDER, taskorder
