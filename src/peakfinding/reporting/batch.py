#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Batch creator for peakfinding reports"
from typing                     import (Optional, Tuple, # pylint: disable=unused-import
                                        Iterator, Union, Iterable, Sequence, cast)

from copy                       import deepcopy
from utils                      import initdefaults
from data.trackio               import checkpath
from model.task                 import Task, TrackReaderTask
from control.processor.batch    import BatchTemplate, PathIO, BatchTask, BatchProcessor
from cordrift.processor         import DriftTask
from eventdetection.processor   import (EventDetectionTask, # pylint: disable=unused-import
                                        ExtremumAlignmentTask)
from peakfinding.processor      import PeakSelectorTask
from .processor                 import PeakFindingExcelTask

class PeakFindingBatchTemplate(BatchTemplate):
    "Template of tasks to run"
    alignment = None # type: Optional[ExtremumAlignmentTask]
    drift     = [DriftTask(onbeads = True)]
    detection = EventDetectionTask()    # type: Optional[EventDetectionTask]
    peaks     = PeakSelectorTask()      # type: Optional[PeakSelectorTask]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __iter__(self) -> Iterator[Task]:
        if self.alignment:
            yield self.alignment
        yield from self.drift
        for i in (self.detection, self.peaks):
            if i is None:
                return
            yield i

class PeakFindingBatchTask(BatchTask):
    "Constructs a list of tasks depending on a template and paths."
    template = PeakFindingBatchTemplate()
    @staticmethod
    def reporttype() -> type:
        "the type of reports"
        return PeakFindingExcelTask

class PeakFindingBatchProcessor(BatchProcessor[PeakFindingBatchTask]):
    """
    Constructs a list of tasks depending on a template and paths.
    """
    @classmethod
    def model(cls, paths: PathIO, modl: PeakFindingBatchTemplate) -> Sequence[Task]:
        "creates a specific model for each path"
        modl = deepcopy(list(iter(modl))) # type: ignore
        modl.insert(0, TrackReaderTask(path = checkpath(paths.track).path, beadsonly = True))
        if paths.reporting not in (None, ''):
            modl.append(cls.tasktype.reporttype()(path = paths.reporting, model = modl))
        return modl

# pylint: disable=invalid-name
createmodels     = PeakFindingBatchProcessor.models
computereporters = PeakFindingBatchProcessor.reports
def generatereports(*paths, template = None, pool = None, **kwa):
    "generates reports"
    for itm in computereporters(*paths, template = template, pool = pool, **kwa):
        tuple(itm)
