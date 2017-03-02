#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Batch creator for hybridstat tasks"
from typing                     import (Optional, Tuple, # pylint: disable=unused-import
                                        Iterator, Union, Iterable, Sequence, cast)
from copy                       import deepcopy
from pathlib                    import Path
import re

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
                                        DistanceConstraint, Constraints)
from peakcalling.tohairpin      import Range
from sequences                  import read as readsequences
from .reporting.processor       import HybridstatExcelTask
from .reporting.identification  import readparams

class HybristatTemplate:
    u"Template of tasks to run"
    alignment = None # type: Optional[ExtremumAlignmentTask]
    drift     = [DriftTask(onbeads = True)]
    events    = EventDetectionTask()    # type: Optional[EventDetectionTask]
    peaks     = PeakSelectorTask()      # type: Optional[PeakSelectorTask]
    identity  = BeadsByHairpinTask()    # type: Optional[BeadsByHairpinTask]
    reporting = HybridstatExcelTask()   # type: Optional[HybridstatExcelTask]

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
        for i in (self.events, self.peaks, self.identity, self.reporting):
            if i is None:
                break
            yield i


ONE_OLIGO      = r'(?P<{}>(?:\[{0,1}[atgc]\]{0,1}){3,4})'
OLIGO_PATTERNS = {1: (r'.*[_-]{}[-_].*'
                      .format(ONE_OLIGO).format('O')),
                  2: (r'.*[_-]{}\+{}[-_].*'
                      .format(ONE_OLIGO.format('O1'), ONE_OLIGO.format('O2'))),
                  '1or2': (r'.*[_-]{}(?:\+{}){{0,1}}[-_].*'
                           .format(ONE_OLIGO.format('O1'), ONE_OLIGO.format('O2')))
                 }

class HybristatIO:
    u"Paths (as regex) on which to run"
    track     = ''                   # type: PATHTYPES
    sequence  = None                 # type: Optional[PATHTYPE]
    idpath    = None                 # type: Optional[PATHTYPE]
    useparams = False
    oligos    = OLIGO_PATTERNS[1]    # type: Union[Sequence[str], str]
    excel     = None                 # type: Optional[PATHTYPE]

class HybristatTask(RootTask):
    u"""
    Constructs a list of tasks depending on a template and paths.
    """
    levelin      = Level.project
    levelou      = Level.peak
    paths        = []                   # type: Sequence[HybristatIO]
    template     = HybristatTemplate()

class HybristatProcessor(Processor):
    u"""
    Constructs a list of tasks depending on a template and paths.
    """
    @staticmethod
    def create(mdl: Sequence[Task]) -> Iterator:
        u"creates a specific model for each path"
        return _create(mdl)

    @classmethod
    def models(cls, paths: HybristatIO, modl: HybristatTemplate) -> Sequence[Task]:
        u"creates a specific model for each path"
        track = TrackReaderTask(path = checkpath(paths.track).path)
        modl  = deepcopy(modl)
        cls.__identity(track, paths, modl)
        cls.__excel   (track, paths, modl)
        return [track]+[i for i in cast(Iterable, modl)]

    def run(self, args):
        cnf = self.config()
        cls = type(self)
        def _run():
            for paths in cnf['paths']:
                modl = cls.model(paths, cnf['template'])
                yield cls.create(modl).run()

        args.apply(_run, levels = self.levels)

    @staticmethod
    def __constraints(paths, idtask):
        idtask.constraints = cstrs = {} # type: Constraints
        if paths.idpath is None:
            return

        for item in readparams(paths.idpath):
            cstrs[item[0]] = DistanceConstraint(item[1], {})
            if len(item) == 2 or not paths.useparams:
                continue

            rngs    = idtask.distances[item[0]]
            stretch = Range(item[2], item[2]+rngs.stretch[-1]*1.01, rngs.stretch[-1])
            bias    = Range(item[3], item[3]+rngs.bias   [-1]*1.01, rngs.bias[-1])
            cstrs[item[0]]['stretch'] = stretch
            cstrs[item[0]]['bias']    = bias

    @staticmethod
    def __oligos(track:TrackReaderTask, oligos:Union[Sequence[str],str]):
        if isinstance(oligos, str):
            trkpath = (track.path,) if isinstance(track.path, str) else track.path
            pattern = re.compile(oligos, re.IGNORECASE)
            for path in trkpath:
                match = pattern.match(path)
                if match is not None:
                    return [i.lower().replace('[','').replace(']', '')
                            for i in match.groups()]

            raise KeyError("Could not find oligo names in {}".format(trkpath))
        return oligos

    @classmethod
    def __identity(cls, track:TrackReaderTask, paths:HybristatIO, modl:HybristatTemplate):
        if not modl.activated('identity'):
            return

        if paths.sequence is None:
            if len(modl.identity.distances) == 0:
                modl.identity = None
            return

        oligos        = cls.__oligos(track, paths.oligos)
        modl.identity = modl.identity.read(paths.sequence, oligos)
        cls.__constraints(paths, modl.identity)

    @staticmethod
    def __excel(track:TrackReaderTask, paths:HybristatIO, modl:HybristatTemplate):
        if not modl.activated('reporting'):
            return

        rep             = modl.reporting
        rep.minduration = modl.events.select.minduration
        rep.hairpins    = modl.identity.distances
        rep.knownbeads  = tuple(modl.identity.constraints.keys())
        rep.sequences   = dict(readsequences(paths.sequence))
        if '*' in rep.path:
            if rep.path.count('*') > 1:
                raise KeyError("could not parse excel output path")
            trk         = track.path[0] if isinstance(track.path, tuple) else track.path
            rep.path    = rep.path.replace('*', Path(trk).stem)
