#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Hybridstat excel reporting processor"
from   typing               import (Sequence,       # pylint: disable=unused-import
                                    Dict, Iterator, Union, Optional, Any)
import pickle

from utils                      import initdefaults
from model                      import Task, Level
from control.processor          import Processor
from control.processor.runner   import pooledinput, pooldump
from anastore                   import dumps
from excelreports.creation      import fileobj

from signalfilter               import rawprecision
from eventdetection             import EventDetectionConfig
from peakcalling.processor      import FitToHairpinTask
from data                       import TrackItems, BEADKEY # pylint: disable=unused-import

from ._base                     import ReporterInfo
from ._summary                  import SummarySheet
from ._peaks                    import PeaksSheet


class HybridstatExcelTask(Task):
    u"Reporter for Hybridstat"
    level       = Level.peak
    path        = ""
    oligos      = []    # type: Sequence[str]
    sequences   = {}    # type: Dict[str,str]
    knownbeads  = None  # type: Optional[Sequence[BEADKEY]]
    minduration = None  # type: Optional[int]

    @initdefaults(frozenset(locals()) - {'level'})
    def __init__(self, **_):
        super().__init__(**_)

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

class HybridstatExcelProcessor(Processor):
    u"Reporter for Hybridstat"
    @staticmethod
    def apply(toframe = None, data = None, pool = None, **kwa):
        "applies the task to a frame or returns a function that does so"
        model = list(data.model)
        kwa['config'] = dumps(model, False) if data is not None else ''

        if pool is None or not any(i.isslow() for i in data):
            def _save(frame):
                run(**kwa, track = frame.track, groups = frame)
                return frame
            save    = _save
        else:
            pickled = pooldump(data)
            def _save(frame):
                rawprecision(frame.track, frame.keys()) # compute & freeze precisions
                run(**kwa, track = frame.track, groups = pooledinput(pool, pickled, frame))
                return frame
            save = _save

        fcn  = lambda frame: frame.new(TrackItems).withdata(save)
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
