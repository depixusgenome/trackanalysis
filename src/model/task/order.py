#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The default order for common tasks"
from typing import Iterable, Iterator, Type
from .base  import Task

TASK_ORDER = ['model.task.RootTask',
              'model.task.track.CycleSamplingTask',
              'cleaning.processor.AberrantValuesTask',
              'cleaning.beadsubtraction.BeadSubtractionTask',
              'model.task.DataSelectionTask',
              'cleaning.processor.DataCleaningTask',
              'eventdetection.processor.ExtremumAlignmentTask',
              'cordrift.processor.DriftTask',
              'eventdetection.processor.EventDetectionTask',
              'peakfinding.processor.PeakSelectorTask',
              'peakcalling.processor.FitToReferenceTask',
              'peakcalling.processor.FitToHairpinTask',
             ]

def taskorder(lst: Iterable[str]) -> Iterator[Type[Task]]:
    "yields a list of task types in the right order"
    for itm in lst:
        modname, clsname = itm[:itm.rfind('.')], itm[itm.rfind('.')+1:]
        yield getattr(__import__(modname, fromlist = (clsname,)), clsname) # type: ignore
