#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"PeakFinding excel reporting processor"
from   typing               import (Sequence,       # pylint: disable=unused-import
                                    Dict, Iterator, Union, Optional, Any)
from   pathlib              import Path
import pickle

from utils                      import initdefaults
from model                      import Task, Level
from control.processor          import Processor
from control.processor.runner   import pooledinput, pooldump
from anastore                   import dumps
from excelreports.creation      import fileobj

from eventdetection             import EventDetectionConfig
from data                       import TrackItems

from ._base                     import ReporterInfo
from ._summary                  import SummarySheet
from ._peaks                    import PeaksSheet

class PeakFindingExcelTask(Task):
    u"Reporter for PeakFinding"
    level       = Level.peak
    path        = ""
    minduration = None  # type: Optional[int]

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

class PeakFindingExcelProcessor(Processor):
    u"Reporter for PeakFinding"
    @staticmethod
    def canpool():
        return True

    @classmethod
    def apply(cls, toframe = None, data = None, pool = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        pick = pooldump(data)
        data = data.append(cls(**kwa))
        path = kwa.pop('path')
        cnf  = dumps(list(data.model), indent = 4, ensure_ascii = False, sort_keys = True)

        def _save(frame):
            if pool is None:
                beads = frame.withaction(lambda i: (i[0], tuple(i[1])))
            else:
                beads = pooledinput(pool, pick, frame).items()
            run(path, cnf, track = frame.track, beads = beads, **kwa)
            return frame

        fcn = lambda frame: frame.new(TrackItems).withdata(_save)
        return fcn if toframe is None else fcn(toframe)

    def run(self, args):
        args.apply(self.apply(**args.poolkwargs(self.task), **self.config()))

def run(path:str, config:str = '', **kwa):
    u"Creates a report."
    self = ReporterInfo(**kwa)
    if str(path).endswith('.pkz'):
        with open(path, 'wb') as book:
            pickle.dump(self, book)
    else:
        with fileobj(path) as book:
            summ = SummarySheet(book, self)

            summ.info(config)
            summ.table ()

            PeaksSheet(book, self).table()
