#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Hybridstat excel reporting processor"
from   typing               import (Sequence, Dict) # pylint: disable=unused-import
import pickle

from utils                  import initdefaults
from model                  import Task, Level
from control.processor      import Processor
from anastore               import dumps
from excelreports.creation  import fileobj

from peakcalling.tohairpin  import Hairpin
from data                   import BEADKEY         # pylint: disable=unused-import

from ._base                 import ReporterInfo
from ._summary              import SummarySheet
from ._peaks                import PeaksSheet


class HybridstatReportTask(Task):
    u"Reporter for Hybridstat"
    level       = Level.peak
    path        = ""
    oligos      = []  # type: Sequence[str]
    sequences   = {}  # type: Dict[str,str]
    knownbeads  = []  # type: Sequence[BEADKEY]
    minduration = 0

    @initdefaults
    def __init__(self, **_):
        super().__init__(**_)

class HybridstatReportProcessor(Processor):
    u"Reporter for Hybridstat"
    def run(self, args):
        hpins = {i: Hairpin(peaks = Hairpin.topeaks(j, self.task.oligos))
                 for i, j in self.task.sequences.items()}

        vals  = self.config()
        vals.update(config   = dumps(args.model, False),
                    hairpins = hpins)

        runonce = False
        def _run(frame):
            vals.update(track  = frame.track,
                        groups = tuple(frame))
            run(**vals)
            nonlocal runonce
            if runonce:
                raise NotImplementedError("Can only run one frame at a time")

        args.apply(_run)

def run(**kwa):
    u"""
    Creates a report.

    Arguments are:

    * *path:*       FILENAME
    * *track:*      Track
    * *config:*     str
    * *groups:*     Sequence[Group]
    * *hairpins:*   Dict[str, Hairpin]
    * *sequences:*  Dict[str, str]
    * *oligos:*     Sequence[str]
    * *knownbeads:* Sequence[BEADKEY]
    * *minduration* float
    """
    self = ReporterInfo(**kwa)
    if str(kwa['path']).endswith('.pkz'):
        with open(kwa['path'], 'wb') as book:
            pickle.dump(self, book)
    else:
        with fileobj(kwa['path']) as book:
            summ = SummarySheet(book, self)

            summ.info(kwa['config'])
            summ.table ()

            PeaksSheet(book, self).table()
