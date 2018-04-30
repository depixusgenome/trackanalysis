#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds quality control displays
"""
import numpy  as np
import pandas as pd

from  utils.decoration                import addproperty
from  data.__scripting__.track        import Track
from  data.__scripting__.tracksdict   import TracksDict

@addproperty(Track, "qc")
class TrackQualityControl:
    """
    Adds items that should be qc'ed.
    """
    def __items__(self, track):
        self._items = track

    def dataframe(self):
        """
        return the temperatures in a  dataframe
        """
        length = np.nanmean(np.diff(self._items.phases[:,0]))
        get    = lambda i, j: getattr(self._items.secondaries, i)[j]
        data   = lambda i: get(i, 'value')
        index  = lambda i: np.int32(np.round(get(i, 'index')/length))

        dframe: pd.DataFrame = None
        for i in ("tservo", "tsink", "tsample"):
            tmp    = pd.DataFrame({i: data(i)}, index = index(i))
            dframe = tmp if dframe is None else dframe.join(tmp) # type: ignore

        vca    = self._items.secondaries.vcap
        dframe = dframe.join(pd.DataFrame({'zmag' : vca['zmag'], 'vcap' : vca['vcap']},
                                          index = index("vcap")))
        return dframe.assign(track = [self._items.key]*len(dframe))

@addproperty(TracksDict, "qc")
class TracksDictQualityControl:
    """
    Adds items that should be qc'ed.
    """
    def dataframe(self):
        """
        return the temperatures in a  dataframe
        """
        return pd.concat([i.qc.dataframe() for i in self._items.values()])

__all__: list = []
