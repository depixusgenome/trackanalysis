#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating FitToHairpinDict for scripting purposes"
from   typing                           import List
from   copy                             import copy as shallowcopy
import pandas                           as pd
from   utils.decoration                 import addto
from   model.__scripting__              import Tasks
from   data                             import Track
from   data.__scripting__.dataframe     import adddataframe
from   control.processor.dataframe      import DataFrameProcessor
from   ..toreference                    import HistogramFit, ChiSquareHistogramFit
from   ..processor                      import (FitToHairpinDict, FitToReferenceDict,
                                                FitToReferenceTask)

def _fit(self, tpe, sequence, oligos, kwa):
    "computes hairpin fits"
    if None not in (sequence, oligos):
        kwa['sequence'] = sequence
        kwa['oligos']   = oligos

    tasks = (Tasks.defaulttasklist(self.path, None, self.cleaned)
             +(getattr(Tasks, tpe)(**kwa),))
    if len(tasks[-1].distances) == 0:
        raise IndexError('No distances found')
    return self.apply(*tasks)

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

adddataframe(FitToHairpinDict, FitToReferenceDict)
__all__: List[str] = ['HistogramFit', 'ChiSquareHistogramFit']
