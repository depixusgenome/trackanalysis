#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Hybridstat excel reporting processor"
from   typing               import Sequence, Dict, Optional
from   pathlib              import Path
from   functools            import partial
import pickle

from utils                  import initdefaults
from model                  import Task, Level
from control.processor      import Processor
from anastore               import dumps
from excelreports.creation  import fileobj

from eventdetection         import EventDetectionConfig
from peakcalling.processor  import FitToHairpinTask
from data.views             import TrackView, BEADKEY

from ._base                 import ReporterInfo
from ._summary              import SummarySheet
from ._peaks                import PeaksSheet

class HybridstatExcelTask(Task):
    "Reporter for Hybridstat"
    level       = Level.peak
    path        = ""
    oligos      : Sequence[str]               = []
    sequences   : Dict[str,str]               = {}
    knownbeads  : Optional[Sequence[BEADKEY]] = None
    minduration : Optional[int]               = None

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

        if self.knownbeads is None:
            identity        = get(FitToHairpinTask)
            self.knownbeads = (tuple(identity.constraints.keys())
                               if identity else tuple())

        if '*' in self.path or Path(self.path).is_dir():
            trkpath = getattr(model[0], 'path', model[0])
            stem    = Path(trkpath[0] if isinstance(trkpath, tuple) else trkpath).stem

            if '*' in self.path:
                if self.path.count('*') > 1:
                    raise IOError("could not parse excel output path", "warning")
                self.path = self.path.replace('*', stem)
            else:
                self.path = str((Path(self.path)/stem).with_suffix('.xlsx'))

class HybridstatExcelProcessor(Processor[HybridstatExcelTask]):
    "Reporter for Hybridstat"
    @staticmethod
    def _save(path, cnf, kwa, frame):
        run(path, cnf, track = frame.track, groups = frame, **kwa)
        return frame

    @classmethod
    def _apply(cls, path, cnf, kwa, frame):
        return frame.new(TrackView).withdata(partial(cls._save, path, cnf, kwa))

    @classmethod
    def apply(cls, toframe = None, model = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        path = kwa.pop('path')
        cnf  = ''
        if model is not None:
            cnf = dumps(list(model), indent = 4, ensure_ascii = False, sort_keys = True)

        return (partial(cls._apply, path, cnf, kwa) if toframe is None else
                cls._apply(path, cnf, kwa, toframe))

    def run(self, args):
        "updates frames"
        args.apply(self.apply(model = args.data.model, **self.config()))

def run(path:str, config:str = '', **kwa):
    "Creates a report."
    self = ReporterInfo(**kwa)
    if str(path).endswith('.pkz'):
        with open(path, 'wb') as book:
            pickle.dump(self, book)
    else:
        with fileobj(path) as book: # type: ignore
            summ = SummarySheet(book, self)

            summ.info(config)
            summ.table ()

            PeaksSheet(book, self).table()
