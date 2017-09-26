#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating FitToHairpinDict for scripting purposes"
import sys
from   typing                           import List, Callable
from   copy                             import copy as shallowcopy
import pandas                           as pd
from   utils.decoration                 import addto
from   data                             import Track
from   control.processor.dataframe      import DataFrameProcessor
from   ..toreference                    import HistogramFit, ChiSquareHistogramFit
from   ..processor                      import (FitToHairpinDict, FitToReferenceDict,
                                                FitToReferenceTask)

Tasks:           type     = sys.modules['model.__scripting__'].Tasks
defaulttasklist: Callable = sys.modules['data.__scripting__'].defaulttasklist

def _fit(self, tpe, sequence, oligos, kwa):
    "computes hairpin fits"
    if None not in (sequence, oligos):
        kwa['sequence'] = sequence
        kwa['oligos']   = oligos

    tasks = (defaulttasklist(self.path, None, self.cleaned)
             +(getattr(Tasks, tpe)(**kwa),))
    if len(tasks[-1].distances) == 0:
        raise IndexError('No distances found')
    return self.apply(*tasks)

@addto(Track) # type: ignore
def fittohairpin(self, sequence = None, oligos = None, **kwa) -> FitToHairpinDict:
    """
    Computes hairpin fits.

    Arguments are for creating the FitToHairpinTask.
    """
    return _fit(self, 'fittohairpin', sequence, oligos, kwa)

@addto(Track) # type: ignore
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

@addto(Track) # type: ignore
def beadsbyhairpin(self, sequence, oligos, **kwa):
    """
    Computes hairpin fits, sorted by best hairpin.

    Arguments are for creating the FitToHairpinTask.
    """
    return _fit(self, 'beadsbyhairpin', sequence, oligos, kwa)

@addto(FitToHairpinDict)
def dataframe(self, **kwa) -> pd.DataFrame:
    """
    converts to a pandas dataframe.
    """
    return DataFrameProcessor.apply(shallowcopy(self), measures = kwa, merge = True)

@addto(FitToReferenceDict)                  # type: ignore
def dataframe(self, **kwa) -> pd.DataFrame: # pylint: disable=function-redefined
    """
    converts to a pandas dataframe.
    """
    return DataFrameProcessor.apply(shallowcopy(self), measures = kwa, merge = True)

__all__: List[str] = ['HistogramFit', 'ChiSquareHistogramFit']
