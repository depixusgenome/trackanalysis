#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   typing    import Union, List, cast

import pandas    as pd
import numpy     as np
import holoviews as hv # pylint: disable=import-error

from   utils     import initdefaults
from   ._trackqc import TrackQC, mostcommonerror, beadqualitysummary

class BeadTrackStatus:
    "display status per bead and track"
    styleopts = dict(xrotation = 40, colorbar  = True, cmap = 'RdYlGn')
    title     = "Most common error per track and bead"
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @staticmethod
    def dataframe(data: Union[TrackQC, pd.DataFrame],
                  tracks: List[str] = None,
                  beads:  List[int] = None) -> pd.DataFrame:
        "The dataframe used for the displays"
        beadqc  = data if isinstance(data, pd.DataFrame) else beadqualitysummary(data)

        frame   = mostcommonerror(beadqc).fillna("").reset_index()
        errlist = sorted(frame.mostcommonerror.unique())
        errlist.remove("")
        errint  = {"":1., **{j: -i/len(errlist) for i, j in enumerate(errlist)}}
        frame['errorid'] = frame.mostcommonerror.apply(errint.__getitem__)

        errint  = {"":0., **{j: -i/len(errlist) for i, j in enumerate(errlist)}}
        frame['errors'] = frame.mostcommonerror.apply(errint.__getitem__)

        for i, j in zip((beads, tracks),('bead', 'track')):
            if i:
                frame.set_index(j, inplace = True)
                frame = frame.loc[list(cast(list, i)), :]
                frame.reset_index(inplace = True)

        ordtracks = list(frame.set_index('track').sort_values('modification').index)
        ordbeads  = list(frame.groupby('bead').errors.sum().sort_values().index)
        ind       = [(i,j) for i in ordtracks for j in ordbeads]
        frame.set_index(['track', 'bead'], inplace = True)
        return frame.join(pd.DataFrame({'order': np.arange(len(ordtracks)*len(ordbeads)),
                                        'track': [i for i, _ in  ind],
                                        'bead':  [i for _, i in ind]})
                          .set_index(['track', 'bead'])).sort_values('order')

    def display(self, data: Union[TrackQC, pd.DataFrame],
                tracks: List[str] = None,
                beads:  List[int] = None) -> pd.DataFrame:
        "Outputs heatmap with the status of the beads per track"
        return hv.HeatMap(
            self.dataframe(data, tracks, beads),
            kdims = ['bead', 'track'],
            vdims = ['errorid', 'mostcommonerror', 'modification']
        ).options(**self.styleopts)

def displaybeadandtrackstatus(data: Union[TrackQC, pd.DataFrame],
                              tracks: List[str] = None,
                              beads:  List[int] = None, **kwa) -> hv.HeatMap:
    "Outputs heatmap with the status of the beads per track"
    return BeadTrackStatus(**kwa).display(data, tracks, beads)
