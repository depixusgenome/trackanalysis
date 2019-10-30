#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The default order for common tasks"
from typing import Iterable, Iterator, Type
from .base  import Task

TASK_ORDER = ['taskmodel.RootTask',
              'taskmodel.track.UndersamplingTask',
              'taskmodel.track.CycleSamplingTask',
              'cleaning.processor.FixedBeadDetectionTask',
              'cleaning.processor.BeadSubtractionTask',
              'taskmodel.DataSelectionTask',
              'cleaning.processor.DataCleaningTask',
              'eventdetection.processor.ExtremumAlignmentTask',
              'cleaning.processor.ClippingTask',
              'cordrift.processor.DriftTask',
              'eventdetection.processor.EventDetectionTask',
              'peakfinding.processor.PeakSelectorTask',
              'peakfinding.processor.SingleStrandTask',
              'peakfinding.processor.BaselinePeakFilterTask',
              'peakfinding.processor.BaselinePeakTask',
              'peakcalling.processor.FitToReferenceTask',
              'peakcalling.processor.FitToHairpinTask',
             ]

def taskorder(lst: Iterable[str]) -> Iterator[Type[Task]]:
    "yields a list of task types in the right order"
    for itm in lst:
        modname, clsname = itm[:itm.rfind('.')], itm[itm.rfind('.')+1:]
        yield getattr(__import__(modname, fromlist = (clsname,)), clsname) # type: ignore
