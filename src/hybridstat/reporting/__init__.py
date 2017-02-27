#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Hybridstat excel reporting"
import pickle
from excelreports.creation  import fileobj
from ._base                 import ReporterInfo
from ._summary              import SummarySheet
from ._peaks                import PeaksSheet

def run(**kwa):
    u"""
    Creates a report.

    Arguments are:

    * *fname:*      FILENAME
    * *track:*      Track
    * *config:*     str
    * *groups:*     Sequence[Group]
    * *hpins:*      Dict[str, Hairpin]
    * *sequences:*  Dict[str, str]
    * *oligos:*     Sequence[str]
    * *knownbeads:* Sequence[BEADKEY]
    * *minduration* float
    """
    self = ReporterInfo(**kwa)
    if str(kwa['fname']).endswith('.pkz'):
        with open(kwa['fname'], 'wb') as book:
            pickle.dump(('hybridstat data', self.state()), book)
    else:
        with fileobj(kwa['fname']) as book:
            summ = SummarySheet(book, self)

            summ.info(kwa['config'])
            summ.table ()

            PeaksSheet(book, self).table()
