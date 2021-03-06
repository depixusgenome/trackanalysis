#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Batch creator for peakfinding reports"
from copy                       import deepcopy
from typing                     import Optional, Iterator, Sequence

from cordrift.processor          import DriftTask
from data.trackio                import checkpath
from eventdetection.processor    import EventDetectionTask, ExtremumAlignmentTask
from peakfinding.processor       import PeakSelectorTask
from taskmodel                   import Task, TrackReaderTask
from taskcontrol.processor.batch import BatchTemplate, PathIO, BatchTask, BatchProcessor
from utils                       import initdefaults
from .processor                  import PeakFindingExcelTask

class PeakFindingBatchTemplate(BatchTemplate):
    "Template of tasks to run"
    alignment: Optional[ExtremumAlignmentTask] = None
    drift                                      = [DriftTask(onbeads = True)]
    detection: Optional[EventDetectionTask]    = EventDetectionTask()
    peaks:     Optional[PeakSelectorTask]      = PeakSelectorTask()
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
        modl.insert(0, TrackReaderTask(path = checkpath(paths.track).path))
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
