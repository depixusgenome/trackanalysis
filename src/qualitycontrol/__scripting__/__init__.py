#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds quality control displays
"""
from   typing                         import Union
import numpy  as np
import pandas as pd

from  utils.decoration                import addproperty
from  data.trackops                   import trackname
from  data.__scripting__.track        import Track
from  data.__scripting__.tracksdict   import TracksDict

def qcdataframe(items: Union[Track, TracksDict])-> pd.DataFrame:
    """
    return the temperatures in a  dataframe
    """
    def _compute(track):
        sizes  = np.diff(np.append(track.phases[:,0], track.nframes+track.phases[0,0]))
        length = np.concatenate([np.full(j, i, dtype = 'i4') for i, j in enumerate(sizes)]
                                +[np.full(1000, -1, dtype = 'i4')])

        get    = lambda i, j: getattr(track.secondaries, i)[j]
        data   = lambda i: get(i, 'value')
        index  = lambda i: (get(i, 'index')-track.phases[0,0]).astype('i4')
        cycle  = lambda i: length[index(i)]

        dframe: pd.DataFrame = None
        for i in ("tservo", "tsink", "tsample"):
            tmp    = pd.DataFrame({i: data(i), 'index': index(i), 'cycle': cycle(i)})
            tmp.set_index(['cycle', 'index'], inplace = True)
            dframe = tmp if dframe is None else dframe.join(tmp, how = 'outer') # type: ignore

        vca    = track.secondaries.vcap
        if vca is None:
            dframe = dframe.assign(zmag = np.full(len(dframe), np.NaN, dtype = 'f4'),
                                   vcap = np.full(len(dframe), np.NaN, dtype = 'f4'))
        else:
            tmp = pd.DataFrame({'zmag' : vca['zmag'], 'vcap' : vca['vcap'],
                                'index': index("vcap"), 'cycle': cycle("vcap")})
            tmp.set_index(['cycle', 'index'], inplace = True)
            dframe = dframe.join(tmp, how = 'outer')
        return dframe.assign(track = np.full(len(dframe), trackname(track)))

    return pd.concat([_compute(i) for i in getattr(items, 'values', lambda : (items,))()])

@addproperty(TracksDict, "qc")
@addproperty(Track, "qc")
class TrackQualityControl:
    """
    Adds items that should be qc'ed.
    """
    def __init__(self, track):
        self._items = track

    def dataframe(self):
        """
        return the temperatures in a  dataframe
        """
        return qcdataframe(self._items)
__all__: list = []
