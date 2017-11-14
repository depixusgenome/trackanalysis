#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds stuff for dataframes"
from   copy                        import copy as shallowcopy
import pandas                      as     pd
from   control.processor.dataframe import DataFrameProcessor


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

    For example, the following code

        >>> track.events.dataframe(begin     = lambda x: np.nanmean(x[:5]),
        ...                        end       = lambda x: np.nanmean(x[-5:])
        ...                        assign    = {'diff': lambda x: x.end.shift(0) - x.begin},
        ...                        transform = lambda x: x.dropna())

    1. Computes z positions at the begining and the end of an event,
    2. computes the difference in z between 2 consecutive events
    3. drops rows with NaN values

    Note that measures (here *begin* and *end*) are created prior to assignations
    which are performed prior to transformations.
    """)

    def dataframe(self, transform = None, assign = None, merge = True, **kwa) -> pd.DataFrame:
        "creates a dataframe"
        transform = ([transform] if callable(transform) else
                     []          if transform is None   else
                     list(transform))

        if assign is not None:
            transform.insert(0, lambda x: x.assign(**assign))

        return DataFrameProcessor.apply(shallowcopy(self),
                                        transform = transform,
                                        measures  = kwa,
                                        merge     = merge)

    dataframe.__doc__ = DataFrameProcessor.factory(classes[0]).__doc__+doc
    classes[0].dataframe = dataframe
