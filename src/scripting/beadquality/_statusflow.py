#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""
from   typing    import List

import holoviews as hv
import pandas    as pd
import numpy     as np

from   ._trackqc import TrackQC, mostcommonerror, beadqualitysummary

class StatusFlow:
    """
    outputs a flow diagram between two tracks showing the proportion
    of the beads classified by their status (their mostCommonError)
    """
    @staticmethod
    def dataframe(trackqc: TrackQC, tracks = None) -> pd.DataFrame:
        "computes the dataframe used for finding edges and nodes"
        col    = mostcommonerror(beadqualitysummary(trackqc))
        frame  = (col.replace(list(set(col.unique()) - {'fixed', 'missing', np.NaN}), 'error')
                  .reset_index()
                  .fillna("ok"))
        frame.sort_values('modification', inplace = True)
        if tracks is all or tracks is Ellipsis:
            return frame

        if tracks is None:
            tracks = trackqc.status.columns[0], trackqc.status.columns[-1]
        return frame[frame.track.apply(lambda x: x in tracks)]

    @staticmethod
    def nodes(frame: pd.DataFrame) -> pd.DataFrame:
        "computes nodes"
        nodes = (frame
                 .groupby(['track', 'modification', 'mostcommonerror'])
                 .bead.count()
                 .reset_index())
        nodes.sort_values(['modification', 'mostcommonerror'], inplace = True)
        nodes.reset_index(inplace = True) # add an 'index' column
        return nodes.rename(columns = {'index': 'nodenumber'})

    @staticmethod
    def edges(frame: pd.DataFrame, nodes: pd.DataFrame) -> pd.DataFrame:
        "computes edges"
        tracks = list(nodes.track.unique())
        nodes  = nodes.set_index(['track', 'mostcommonerror'])
        errors = frame.pivot(index = 'bead', columns = 'track', values = 'mostcommonerror')
        errors.reset_index(inplace = True)

        edges  = pd.DataFrame(columns = ['From', 'To', 'bead'])
        for i in range(len(tracks)-1):
            tmp = (errors.groupby(list(tracks[i:i+2])).bead.count()
                   .reset_index())
            for j, k in zip(('From', 'To'), tracks[i:i+2]):
                tmp[j] = [nodes.loc[k, l].nodenumber for l in tmp[k]]
            tmp   = tmp.rename(columns = {tracks[i]: 'Left', tracks[i+1]: 'Right'})
            edges = pd.concat([edges, tmp])
        return edges

    @classmethod
    def display(cls, trackqc: TrackQC, tracks: List[str] = None):
        """
        outputs a flow diagram between two tracks showing the proportion
        of the beads classified by their status (their mostCommonError)
        """
        frame   = cls.dataframe(trackqc, tracks)
        nodes   = cls.nodes(frame)
        edges   = cls.edges(frame, nodes)
        return (hv.Sankey((edges, hv.Dataset(nodes, "nodenumber")),
                          ['From', 'To'], ['bead', 'Left'])
                .options(label_index      = 'mostcommonerror',
                         edge_color_index = 'Left',
                         color_index      = 'mostcommonerror'))

def displaystatusflow(trackqc: TrackQC, tracks: List[str] = None):
    """
    outputs a flow diagram between two tracks showing the proportion
    of the beads classified by their status (their mostCommonError)
    """
    return StatusFlow.display(trackqc, tracks)

__all__ = ['displaystatusflow']
