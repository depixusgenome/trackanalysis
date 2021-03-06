#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Batch creator for hybridstat tasks"
from typing                         import (
    Optional, Dict, Iterator, Union, Sequence, Iterable, cast
)
from copy                           import deepcopy
from pathlib                        import Path
import re

from data.trackio                   import checkpath, PATHTYPE
from peakfinding.reporting.batch    import PeakFindingBatchTemplate
from peakcalling                    import Range
from peakcalling.processor          import (
    BeadsByHairpinTask, FitToHairpinTask, DistanceConstraint, Constraints
)
from taskmodel                      import Task, TrackReaderTask
from taskcontrol.processor.batch    import BatchTask, BatchProcessor, PathIO
from utils                          import initdefaults
from .processor                     import HybridstatExcelTask
from .identification                import readparams

def readconstraints(idtask      : FitToHairpinTask,
                    idpath      : Union[Path, str, None],
                    useparams   : bool  = True,
                    constraints : Dict[str, Range] = None) -> FitToHairpinTask :
    "adds constraints to an identification task"
    cstrs: Constraints = {}
    idtask.constraints = cstrs
    if idpath is None or not Path(idpath).exists():
        return idtask

    deflt = dict(FitToHairpinTask.DEFAULT_CONSTRAINTS)
    deflt.update(constraints if constraints else {})
    for item in readparams(cast(str, idpath)):
        cstrs[item[0]] = DistanceConstraint(item[1], {})
        if len(item) == 2 or not useparams:
            continue

        if item[2] is not None:
            cstrs[item[0]].constraints['stretch'] = Range(item[2], *deflt['stretch'][1:3])

        if item[3] is not None:
            cstrs[item[0]].constraints['bias'] = Range(item[3], *deflt['bias'][1:3])
    return idtask

def fittohairpintask(seqpath     : Union[Path, str],
                     oligos      : Union[Sequence[str], str],
                     idpath      : Union[None,Path,str] = None,
                     useparams   : bool                 = True,
                     constraints : Dict[str, Range]     = None,
                     **kwa) -> FitToHairpinTask:
    "creates and identification task from paths"
    task = FitToHairpinTask.read(seqpath, oligos, **kwa)
    if len(task.fit) == 0:
        raise IOError("Could not find any sequence in "+str(seqpath))
    return readconstraints(task, idpath, useparams, constraints)

def beadsbyhairpintask(seqpath     : Union[Path, str],
                       oligos      : Union[Sequence[str], str],
                       idpath      : Union[None,Path,str] = None,
                       useparams   : bool                 = True,
                       constraints : Dict[str, Range]     = None,
                       **kwa) -> BeadsByHairpinTask:
    "creates and identification task from paths"
    task = fittohairpintask(seqpath, oligos, idpath, useparams, constraints, **kwa)
    return BeadsByHairpinTask(**task.config())

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
    sequence: Optional[PATHTYPE]      = None
    idpath:   Optional[PATHTYPE]      = None
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

class HybridstatBatchProcessor(BatchProcessor[HybridstatBatchTask]):
    """
    Constructs a list of tasks depending on a template and paths.
    """
    @classmethod
    def model(cls,  # type: ignore
              paths : HybridstatIO,
              modl  : HybridstatTemplate) -> Sequence[Task]:
        "creates a specific model for each path"
        modl    = deepcopy(modl)

        track   = TrackReaderTask(path = checkpath(paths.track).path)
        oligos  = cls.__oligos(track, paths.oligos)
        cls.__identity(oligos, paths, modl)

        model = [cast(Task, track)] + list(cast(Iterator[Task], modl))
        excel = cls.__excel (oligos, track, paths, modl)
        return model+ ([cast(Task, excel)] if excel else [])

    @staticmethod
    def __oligos(track:TrackReaderTask, oligos:Union[Sequence[str],str]):
        if isinstance(oligos, str):
            trkpath = (track.path,) if isinstance(track.path, str) else track.path
            pattern = re.compile(oligos, re.IGNORECASE)
            for path in cast(Iterable[str], trkpath):
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
            if len(getattr(modl.identity, 'fit')) == 0:
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
