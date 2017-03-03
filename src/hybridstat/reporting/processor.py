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
from data                   import BEADKEY, Track

from ._base                 import ReporterInfo, Group
from ._summary              import SummarySheet
from ._peaks                import PeaksSheet


class HybridstatExcelTask(Task):
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

class HybridstatExcelProcessor(Processor):
    u"Reporter for Hybridstat"
    def run(self, args):
        hpins = {i: Hairpin(peaks = Hairpin.topeaks(j, self.task.oligos))
                 for i, j in self.task.sequences.items()}

        vals  = self.config()
        vals.update(config   = dumps(args.model, False),
                    hairpins = hpins)

        def _run(frame):
            vals.update(track  = frame.track,
                        groups = [i for _, i in frame])
            run(**vals)
            yield frame

        args.apply(_run)

def run(path:        str,       # pylint: disable=too-many-arguments
        track:       Track,
        config:      str,
        groups:      Sequence[Group],
        hairpins:    Dict[str, Hairpin],
        sequences:   Dict[str, str],
        oligos:      Sequence[str],
        knownbeads:  Sequence[BEADKEY],
        minduration: float,
        **_):
    u" Creates a report. "
    self = ReporterInfo(track       = track,
                        groups      = groups,
                        hairpins    = hairpins,
                        sequences   = sequences,
                        oligos      = oligos,
                        knownbeads  = knownbeads,
                        minduration = minduration)
    if str(path).endswith('.pkz'):
        with open(path, 'wb') as book:
            pickle.dump(self, book)
    else:
        with fileobj(path) as book:
            summ = SummarySheet(book, self)

            summ.info(config)
            summ.table ()

            PeaksSheet(book, self).table()
