#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"PeakFinding excel reporting processor"
from   typing               import Optional, Iterator
from   pathlib              import Path
import pickle

from excelreports.creation        import fileobj

from eventdetection               import EventDetectionConfig
from taskmodel                    import Task, Level
from taskcontrol.processor        import Processor
from taskcontrol.processor.runner import pooledinput, pooldump
from utils                        import initdefaults

from ._base                       import ReporterInfo
from ._summary                    import SummarySheet
from ._peaks                      import PeaksSheet

class PeakFindingExcelTask(Task):
    u"Reporter for PeakFinding"
    level                      = Level.peak
    path                       = ""
    minduration: Optional[int] = None

    @initdefaults(frozenset(locals()) - {'level'},
                  model = lambda self, i: self.frommodel(i))
    def __init__(self, **kwa):
        super().__init__(**kwa)

    @classmethod
    def isslow(cls) -> bool:
        "whether this task implies long computations"
        return True

    def frommodel(self, model):
        "initialises from model"
        get = lambda x: next((i for i in model[::-1] if isinstance(model, x)), None)
        if self.minduration is None:
            detection        = get(EventDetectionConfig)
            self.minduration = (detection.events.select.minduration
                                if detection else 0.)

        trk  = model[0]
        if self.path is not None and '*' in self.path:
            if self.path.count('*') > 1:
                raise IOError("could not parse excel output path", "warning")
            trk       = getattr(trk, 'path', trk)
            trk       = trk[0] if isinstance(trk, tuple) else trk
            self.path = self.path.replace('*', Path(trk).stem)

class PeakFindingExcelProcessor(Processor[PeakFindingExcelTask]):
    u"Reporter for PeakFinding"
    @staticmethod
    def canpool():
        "returns whether this is pooled"
        return True

    @classmethod
    def apply(cls, toframe = None, data = None, pool = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        pick = pooldump(data)
        data = data.append(cls(**kwa))
        path = kwa.pop('path')
        cnf  = list(data.model)

        def _save(frame):
            beads = {}
            for i, j in pooledinput(pool, pick, frame, safe = True).items():
                try:
                    beads[i] = tuple(j) if isinstance(j, Iterator) else j
                except Exception as exc: # pylint: disable=broad-except
                    beads[i] = exc
            run(path, cnf, track = frame.track, beads = beads, **kwa)

        return _save if toframe is None else _save(toframe)

    def run(self, args):
        "updates frames"
        args.apply(self.apply(**args.poolkwargs(self.task), **self.config()))

def run(path:str, config = '', **kwa):
    u"Creates a report."
    self = ReporterInfo(**kwa)
    if str(path).endswith('.pkz'):
        with open(path, 'wb') as book:
            pickle.dump(self, book)
    else:
        with fileobj(path) as book:
            summ = SummarySheet(book, self)

            summ.info(config)
            summ.table()
            summ.footer()

            PeaksSheet(book, self).table()
