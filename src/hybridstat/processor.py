#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Batch creator for hybridstat tasks"
from typing                     import (Optional, Tuple, # pylint: disable=unused-import
                                        Iterator, Union, Iterable, Sequence, cast)
from copy                       import deepcopy
from pathlib                    import Path
import re

from utils                      import initdefaults
from data.trackio               import (checkpath,       # pylint: disable=unused-import
                                        PATHTYPES, PATHTYPE)
from model.task                 import RootTask, Task, Level, TrackReaderTask
from control.taskcontrol        import create as _create
from control.processor          import Processor
from cordrift.processor         import DriftTask
from eventdetection.processor   import (EventDetectionTask, # pylint: disable=unused-import
                                        ExtremumAlignmentTask)
from peakfinding.processor      import PeakSelectorTask
from peakcalling.processor      import (BeadsByHairpinTask, # pylint: disable=unused-import
                                        FitToHairpinTask, DistanceConstraint,
                                        Constraints)
from peakcalling.tohairpin      import Range
from sequences                  import read as readsequences
from .reporting.processor       import HybridstatExcelTask
from .reporting.identification  import readparams

def readconstraints(idtask   : FitToHairpinTask,
                    idpath   : Union[Path, str, None],
                    useparams: bool = True) -> FitToHairpinTask:
    "adds constraints to an identification task"
    cstrs              = {} # type: Constraints
    idtask.constraints = cstrs
    if idpath is None or not Path(idpath).exists():
        return idtask

    for item in readparams(idpath):
        cstrs[item[0]] = DistanceConstraint(item[1], {})
        if len(item) == 2 or not useparams:
            continue

        rngs    = idtask.distances[item[0]]
        if item[2] is not None:
            stretch = Range(item[2], rngs.stretch[-1]*.1, rngs.stretch[-1])
            cstrs[item[0]]['stretch'] = stretch

        if item[3] is not None:
            bias    = Range(item[3], rngs.bias   [-1]*.1, rngs.bias[-1])
            cstrs[item[0]]['bias']    = bias
    return idtask

def fittohairpintask(seqpath    : Union[Path, str],
                     oligos     : Union[Sequence[str], str],
                     idpath     : Union[None,Path,str] = None,
                     useparams  : bool = True) -> FitToHairpinTask:
    "creates and identification task from paths"
    task = FitToHairpinTask.read(seqpath, oligos)
    if len(task.distances) == 0:
        raise IOError("Could not find any sequence in "+str(seqpath))
    return readconstraints(task, idpath, useparams)

class HybridstatTemplate:
    u"Template of tasks to run"
    alignment = None # type: Optional[ExtremumAlignmentTask]
    drift     = [DriftTask(onbeads = True)]
    detection = EventDetectionTask()    # type: Optional[EventDetectionTask]
    peaks     = PeakSelectorTask()      # type: Optional[PeakSelectorTask]
    identity  = BeadsByHairpinTask()    # type: Optional[BeadsByHairpinTask]
    @initdefaults
    def __init__(self, **kwa):
        pass

    def activated(self, aobj:Union[str,Task]) -> bool:
        u"Wether the task will be called"
        obj = getattr(self, aobj) if isinstance(aobj, str) else aobj
        for i in self.__iter__():
            if i is obj:
                return True
        return False

    def __iter__(self) -> Iterator[Task]:
        if self.alignment:
            yield self.alignment
        yield from self.drift
        for i in (self.detection, self.peaks, self.identity):
            if i is None:
                return
            yield i

ONE_OLIGO      = r'(?P<{}>(?:\[{{0,1}}[atgc]\]{{0,1}}){{3,4}})'
OLIGO_PATTERNS = {1: (r'.*[_-]{}[-_].*'
                      .format(ONE_OLIGO).format('O')),
                  2: (r'.*[_-]{}\+{}[-_].*'
                      .format(ONE_OLIGO.format('O1'), ONE_OLIGO.format('O2'))),
                  '1or2': (r'.*[_-]{}(?:\+{}){{0,1}}[-_].*'
                           .format(ONE_OLIGO.format('O1'), ONE_OLIGO.format('O2')))
                 }

class HybridstatIO:
    u"Paths (as regex) on which to run"
    track     = ''                   # type: PATHTYPES
    sequence  = None                 # type: Optional[PATHTYPE]
    idpath    = None                 # type: Optional[PATHTYPE]
    useparams = False
    oligos    = OLIGO_PATTERNS[1]    # type: Union[Sequence[str], str]
    reporting = None                 # type: Optional[PATHTYPE]
    @initdefaults
    def __init__(self, **kwa):
        pass

class HybridstatTask(RootTask):
    u"""
    Constructs a list of tasks depending on a template and paths.
    """
    levelin      = Level.project
    levelou      = Level.peak
    paths        = []                   # type: Sequence[HybridstatIO]
    template     = HybridstatTemplate()
    @initdefaults
    def __init__(self, **kwa):
        super().__init__(**kwa)

    def addpaths(self, **kwa):
        u"appends a HybridstatIO to the list"
        self.paths.append(HybridstatIO(**kwa))

class HybridstatProcessor(Processor):
    u"""
    Constructs a list of tasks depending on a template and paths.
    """
    @staticmethod
    def create(mdl: Sequence[Task]) -> Iterator:
        u"creates a specific model for each path"
        return _create(mdl)

    @classmethod
    def models(cls, paths: HybridstatIO, modl: HybridstatTemplate) -> Sequence[Task]:
        u"creates a specific model for each path"
        track   = TrackReaderTask(path = checkpath(paths.track).path, beadsonly = True)
        modl    = deepcopy(modl)
        oligos  = cls.__oligos(track, paths.oligos)
        cls.__identity(oligos, paths, modl)
        rep     = cls.__excel (oligos, track, paths, modl)
        if rep is None:
            return [track]+[i for i in cast(Iterable, modl)]
        else:
            return [track]+[i for i in cast(Iterable, modl)] + [rep]

    def run(self, args):
        cnf = self.config()
        cls = type(self) # type: HybridstatProcessor
        def _run():
            for paths in cnf['paths']:
                modl = cls.models(paths, cnf['template'])
                yield from cls.create(modl).run()

        args.apply(_run, levels = self.levels)

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

            raise KeyError("Could not find oligo names in {}".format(trkpath))
        return oligos

    @classmethod
    def __identity(cls, oligos:Sequence[str], paths:HybridstatIO, modl:HybridstatTemplate):
        if not modl.activated('identity'):
            return

        if paths.sequence is None:
            if len(modl.identity.distances) == 0:
                modl.identity = None
            return

        modl.identity = fittohairpintask(paths.sequence, oligos,
                                         paths.idpath, paths.useparams)

    @staticmethod
    def __excel(oligos: Sequence[str],
                track : TrackReaderTask,
                paths : HybridstatIO,
                modl  : HybridstatTemplate) -> Optional[HybridstatExcelTask]:
        if paths.reporting in (None, ''):
            return None
        rep = HybridstatExcelTask(minduration = modl.detection.events.select.minduration,
                                  hairpins    = modl.identity.distances,
                                  knownbeads  = tuple(modl.identity.constraints.keys()),
                                  sequences   = dict(readsequences(paths.sequence)),
                                  oligos      = oligos,
                                  path        = paths.reporting)
        if '*' in rep.path:
            if rep.path.count('*') > 1:
                raise KeyError("could not parse excel output path")
            trk         = track.path[0] if isinstance(track.path, tuple) else track.path
            rep.path    = rep.path.replace('*', Path(trk).stem)
        return rep
