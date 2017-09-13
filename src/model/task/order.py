#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"The default order for common tasks"
TASK_ORDER = ['model.task.RootTask',
              'model.task.DataSelectionTask',
              'cleaning.beadsubtraction.BeadSubtractionTask',
              'cleaning.processor.DataCleaningTask',
              'eventdetection.processor.ExtremumAlignmentTask',
              'cordrift.processor.DriftTask',
              'eventdetection.processor.EventDetectionTask',
              'peakfinding.processor.PeakSelectorTask',
              'peakcalling.processor.FitToHairpinTask',
             ]

def taskorder(lst):
    "yields a list of task types in the right order"
    for itm in lst:
        modname, clsname = itm[:itm.rfind('.')], itm[itm.rfind('.')+1:]
        yield getattr(__import__(modname, fromlist = (clsname,)), clsname) # type: ignore
