#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating FitToHairpinDict for scripting purposes"
from   typing                           import List, Union, Iterator, Iterable
from   copy                             import copy as shallowcopy

import pandas                           as pd
import numpy                            as np

from   utils.decoration                 import addto
from   model.__scripting__              import Tasks
from   data                             import Track
from   data.__scripting__.dataframe     import adddataframe
from   peakfinding.__scripting__        import Detailed
from   control.processor.dataframe      import DataFrameProcessor
from   ..toreference                    import HistogramFit, ChiSquareHistogramFit
from   ..processor                      import (FitToHairpinDict, FitToReferenceDict,
                                                FitToReferenceTask, FitToHairpinTask)
@addto(FitToReferenceTask)
def __scripting_save__(self):
    self.fitdata.clear()

def _fit(self, tpe, sequence, oligos, kwa):
    "computes hairpin fits"
    if None not in (sequence, oligos):
        kwa['sequence'] = sequence
        kwa['oligos']   = oligos

    last  = getattr(Tasks, tpe)(**kwa)
    if not last.distances:
        raise IndexError('No distances found')
    return self.apply(*Tasks.defaulttasklist(self, None), *last)

@addto(Track)
def fittohairpin(self, sequence = None, oligos = None, **kwa) -> FitToHairpinDict:
    """
    Computes hairpin fits.

    Arguments are for creating the FitToHairpinTask.
    """
    return _fit(self, 'fittohairpin', sequence, oligos, kwa)

@addto(Track)
def fittoreference(self, task: FitToReferenceTask = None, **kwa) -> FitToReferenceDict:
    """
    Computes fits to a reference.

    Arguments are for creating the FitToReferenceTask.
    """
    if task is not None and len(kwa):
        raise NotImplementedError()
    return self.apply(Tasks.peakselector, # type: ignore
                      (task if isinstance(task, FitToReferenceTask) else
                       FitToReferenceTask(**kwa)))

@addto(Track)
def beadsbyhairpin(self, sequence, oligos, **kwa):
    """
    Computes hairpin fits, sorted by best hairpin.

    Arguments are for creating the FitToHairpinTask.
    """
    return _fit(self, 'beadsbyhairpin', sequence, oligos, kwa)

@addto(FitToReferenceDict)
def detailed(self, ibead, precision: float = None) -> Union[Iterator[Detailed], Detailed]:
    "detailed output from config"
    if ibead is Ellipsis:
        return iter(self.detailed(i, precision) for i in self.keys())
    if isinstance(ibead, Iterable):
        return iter(self.detailed(i, precision) for i in set(self.keys) & set(ibead))
    if isinstance(self.data, FitToReferenceDict):
        if self.actions:
            raise NotImplementedError()
        return self.data.detailed(ibead, precision) # type: ignore

    dtl  = self.data.detailed(ibead, precision)
    out  = self[...].withdata({ibead: dtl.output}).compute(ibead)
    dtl.setparams(out.params)
    return dtl

adddataframe(FitToHairpinDict, FitToReferenceDict)
__all__: List[str] = ['HistogramFit', 'ChiSquareHistogramFit', 'FitToReferenceTask',
                      'FitToHairpinTask']
