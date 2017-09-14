#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Batch creator for hybridstat tasks"
from typing                         import Optional, Iterator, Union, Sequence, cast
from copy                           import deepcopy
from pathlib                        import Path
import re

from utils                          import initdefaults
from data.trackio                   import checkpath, PATHTYPE

from model.task                     import Task, TrackReaderTask
from control.processor.batch        import BatchTask, BatchProcessor, PathIO
from peakfinding.reporting.batch    import PeakFindingBatchTemplate
from peakcalling                    import Range
from peakcalling.tohairpin          import GaussianProductFit
from peakcalling.processor          import (BeadsByHairpinTask, # pylint: disable=unused-import
                                            FitToHairpinTask, DistanceConstraint,
                                            Constraints)
from .processor                     import HybridstatExcelTask
from .identification                import readparams

def readconstraints(idtask   : FitToHairpinTask,
                    idpath   : Union[Path, str, None],
                    useparams: bool = True) -> FitToHairpinTask:
    "adds constraints to an identification task"
    cstrs              = {} # type: Constraints
    idtask.constraints = cstrs
    if idpath is None or not Path(idpath).exists():
        return idtask

    for item in readparams(cast(str, idpath)):
        cstrs[item[0]] = DistanceConstraint(item[1], {})
        if len(item) == 2 or not useparams:
            continue

        rngs = idtask.distances.get(item[1], GaussianProductFit())
        if item[2] is not None:
            stretch = Range(item[2], rngs.stretch[-1]*.1, rngs.stretch[-1])
            cstrs[item[0]].constraints['stretch'] = stretch

        if item[3] is not None:
            bias = Range(item[3], rngs.bias   [-1]*.1, rngs.bias[-1])
            cstrs[item[0]].constraints['bias'] = bias
    return idtask

def fittohairpintask(seqpath    : Union[Path, str],
                     oligos     : Union[Sequence[str], str],
                     idpath     : Union[None,Path,str] = None,
                     useparams  : bool                 = True,
                     **kwa) -> FitToHairpinTask:
    "creates and identification task from paths"
    task = FitToHairpinTask.read(seqpath, oligos, **kwa)
    if len(task.distances) == 0:
        raise IOError("Could not find any sequence in "+str(seqpath))
    return readconstraints(task, idpath, useparams)

def beadsbyhairpintask(seqpath    : Union[Path, str],
                       oligos     : Union[Sequence[str], str],
                       idpath     : Union[None,Path,str] = None,
                       useparams  : bool = True) -> BeadsByHairpinTask:
    "creates and identification task from paths"
    tsk = fittohairpintask(seqpath, oligos, idpath, useparams)
    return BeadsByHairpinTask(**tsk.config())

class HybridstatTemplate(PeakFindingBatchTemplate):
    "Template of tasks to run"
    identity: Optional[BeadsByHairpinTask] = BeadsByHairpinTask()
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def __iter__(self) -> Iterator[Task]:
        yield from super().__iter__()
        if self.identity is not None:
            yield self.identity

ONE_OLIGO      = r'(?P<{}>(?:\[{{0,1}}[atgc]\]{{0,1}}){{3,4}})'
OLIGO_PATTERNS = {1: (r'.*[_-]{}[-_].*'
                      .format(ONE_OLIGO).format('O')),
                  2: (r'.*[_-]{}\+{}[-_].*'
                      .format(ONE_OLIGO.format('O1'), ONE_OLIGO.format('O2'))),
                  '1or2': (r'.*[_-]{}(?:\+{}){{0,1}}[-_].*'
                           .format(ONE_OLIGO.format('O1'), ONE_OLIGO.format('O2')))
                 }

class HybridstatIO(PathIO):
    "Paths (as regex) on which to run"
    sequence: PATHTYPE                = None
    idpath:   PATHTYPE                = None
    useparams                         = False
    oligos: Union[Sequence[str], str] = OLIGO_PATTERNS[1]
    @initdefaults(frozenset(locals()))
    def __init__(self, **kwa):
        super().__init__(**kwa)

class HybridstatBatchTask(BatchTask):
    """
    Constructs a list of tasks depending on a template and paths.
    """
    template = HybridstatTemplate()
    @staticmethod
    def pathtype() -> type:
        "the type of paths"
        return HybridstatIO

    @staticmethod
    def reporttype() -> type:
        "the type of reports"
        return HybridstatExcelTask

class HybridstatBatchProcessor(BatchProcessor):
    """
    Constructs a list of tasks depending on a template and paths.
    """
    @classmethod
    def model(cls, paths: HybridstatIO, modl: HybridstatTemplate) -> Sequence[Task]:
        "creates a specific model for each path"
        modl    = deepcopy(modl)

        track   = TrackReaderTask(path = checkpath(paths.track).path, beadsonly = True)
        oligos  = cls.__oligos(track, paths.oligos)
        cls.__identity(oligos, paths, modl)

        model = [track] + list(modl) + [cls.__excel (oligos, track, paths, modl)]
        return model[:-1 if model[-1] is None else None]

    @staticmethod
    def __oligos(track:TrackReaderTask, oligos:Union[Sequence[str],str]):
        if isinstance(oligos, str):
            trkpath = (track.path,) if isinstance(track.path, str) else track.path
            pattern = re.compile(oligos, re.IGNORECASE)
            for path in trkpath:
                match = pattern.match(str(path))
                if match is not None:
                    return [i.lower().replace('[','').replace(']', '')
                            for i in match.groups()]

            raise KeyError("Could not find oligo names in {}".format(trkpath),
                           "warning")
        return oligos

    @classmethod
    def __identity(cls, oligos:Sequence[str], paths:HybridstatIO, modl:HybridstatTemplate):
        if not modl.activated('identity'):
            return

        if paths.sequence is None:
            if len(modl.identity.distances) == 0:
                modl.identity = None
            return

        modl.identity = beadsbyhairpintask(paths.sequence, oligos,
                                           paths.idpath, paths.useparams)

    @staticmethod
    def __excel(oligos: Sequence[str],
                track : TrackReaderTask,
                paths : HybridstatIO,
                modl  : HybridstatTemplate) -> Optional[HybridstatExcelTask]:
        if paths.reporting not in (None, ''):
            return HybridstatExcelTask(sequences = paths.sequence,
                                       oligos    = oligos,
                                       path      = paths.reporting,
                                       model     = [track] + list(modl))
        return None

# pylint: disable=invalid-name
createmodels     = HybridstatBatchProcessor.models
computereporters = HybridstatBatchProcessor.reports
def generatereports(*paths, template = None, pool = None, **kwa):
    "generates reports"
    for itm in computereporters(*paths, template = template, pool = pool, **kwa):
        tuple(itm)
