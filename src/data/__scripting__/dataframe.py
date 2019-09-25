#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds stuff for dataframes"
from   typing                      import Dict
from   copy                        import copy as shallowcopy
import pandas                      as     pd
import numpy                       as     np
from   utils.decoration            import addto
from   taskcontrol.processor.dataframe import SafeDataFrameProcessor, DataFrameTask
from   ..views                     import Cycles, Beads

@addto(Beads)
def dataframe(self):
    """
    Creates a dataframe with as many columns as there are beads.

    Columns *cycle* and *phase* are also added.
    """
    allpha = self.phases
    phase  = np.zeros(self.nframes, 0, dtype = 'i4')
    npha   = self.track.nphases
    for i, j in enumerate(np.split(phase, allpha.ravel()[1:])):
        j[:] = i % npha

    cycle  = np.zeros(self.nframes, 0, dtype = 'i4')
    for i, j in enumerate(np.split(phase, allpha[1:,0])):
        j[:] = i // npha

    info = {ibead: data for ibead, data in self}
    info.update(phase = phase, cycle = cycle)
    return pd.DataFrame(info)

@addto(Cycles)       # type: ignore
def dataframe(self): # pylint: disable=function-redefined
    """
    Creates a dataframe with as many columns as there are beads and cycles.

    NaN values are appended to the end phases should they be too short.
    """
    first  = self.first          if self.first        else 0
    last   = self.track.nphases  if self.last is None else self.last+1
    if last > 7:
        raise NotImplementedError("keep last phase < 7")
    durs   = np.array([self.track.phase.duration(..., i) for i in range(first, last)],
                      dtype = 'i4').T
    starts = np.cumsum([0]+ [np.max(i) for i in durs.T])

    info: Dict[str,np.array] = {}
    for (ibead, icycle), vals in self:
        arr = np.full(starts[-1], np.NaN, dtype = 'f4')
        for i, j in zip(starts, np.split(vals, durs[icycle].cumsum())):
            arr[i:i+len(j)] = j
        info[f"b{ibead}c{icycle}"] = arr
    return pd.DataFrame(info)

def adddataframe(*classes):
    "Adds a dataframe method to the class"
    if len(classes) > 1:
        for cls in classes:
            adddataframe(cls)

    # pylint: disable=bad-continuation
    doc = (
    """
    It's also possible to transform the pd.DataFrame every iteration or assign
    new values.

    For example, the following code:

    ```python
    >>> track.events.dataframe(begin     = lambda x: np.nanmean(x[:5]),
    ...                        end       = lambda x: np.nanmean(x[-5:])
    ...                        assign    = {'diff': lambda x: x.end.shift(0) - x.begin},
    ...                        transform = lambda x: x.dropna())
    ```

    1. Computes z positions at the begining and the end of an event,
    2. computes the difference in z between 2 consecutive events
    3. drops rows with NaN values

    Note that measures (here *begin* and *end*) are created prior to assignations
    which are performed prior to transformations.
    """)

    # pylint: disable=redefined-outer-name
    def dataframe(self, transform = None, assign = None, merge = True, **kwa) -> pd.DataFrame:
        "creates a dataframe"
        transform = ([transform] if callable(transform) else
                     []          if transform is None   else
                     list(transform))

        if assign is not None:
            transform.insert(0, lambda x: x.assign(**assign))

        data = SafeDataFrameProcessor.apply(
            shallowcopy(self),
            transform = transform,
            measures  = kwa,
            merge     = merge
        )
        if data is None:
            return None

        lst = [
            *self.tasklist,
            DataFrameTask(
                transform = transform,
                measures  = kwa,
                merge     = merge
            )
        ]
        data.__dict__['tasklist'] = lst
        if 'tasklist' not in getattr(data, '_metadata'):
            getattr(data, '_metadata').append('tasklist')
        return data

    dataframe.__doc__ = SafeDataFrameProcessor.factory(classes[0]).__doc__+doc
    classes[0].dataframe = dataframe
