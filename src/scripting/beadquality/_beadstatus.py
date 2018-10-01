#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   typing    import Union, List, cast

import holoviews as hv
import pandas    as pd

from   utils     import initdefaults
from   ._trackqc import TrackQC, mostcommonerror, beadqualitysummary

class BeadTrackStatus:
    "display status per bead and track"
    plotopts  = dict(xrotation = 40, colorbar  = True)
    styleopts = dict(cmap      = 'RdYlGn')
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

        for i, j in zip((beads, tracks),('bead', 'track')):
            if i:
                frame.set_index(j, inplace = True)
                frame = frame.loc[list(cast(list, i)), :]
                frame.reset_index(inplace = True)
        return frame

    def display(self, data: Union[TrackQC, pd.DataFrame],
                tracks: List[str] = None,
                beads:  List[int] = None) -> pd.DataFrame:
        "Outputs heatmap with the status of the beads per track"
        return (hv.HeatMap(self.dataframe(data, tracks, beads),
                           kdims = ['bead', 'track'],
                           vdims = ['errorid', 'mostcommonerror'])
                (plot  = self.plotopts, style = self.styleopts))

def displaybeadandtrackstatus(data: Union[TrackQC, pd.DataFrame],
                              tracks: List[str] = None,
                              beads:  List[int] = None, **kwa) -> hv.HeatMap:
    "Outputs heatmap with the status of the beads per track"
    return BeadTrackStatus(**kwa).display(data, tracks, beads)
