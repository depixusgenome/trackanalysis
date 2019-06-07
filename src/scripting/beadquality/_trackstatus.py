#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   typing    import Union, List

import pandas    as pd
import numpy     as np
import holoviews as hv  # pylint: disable=import-error

from   utils     import initdefaults
from   ._trackqc import TrackQC, mostcommonerror, beadqualitysummary

class TrackStatus:
    """
    Outputs a heatmap. Columns are types of Error and rows are tracks. Each
    cell presents the percentage of appearance of the specific error at the
    specific track.
    """
    params = 'ok', 'fixed', 'missing'
    styleopts = dict(cmap = 'RdYlGn', tools = ['hover'], xrotation = 40, colorbar = True)
    title     = 'By track, the percentage of beads per status & error'
    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @staticmethod
    def value(normalize) -> str:
        "return the parameter name depending on normalization"
        return 'percentage' if normalize else 'count'

    def dataframe(self, data: Union[TrackQC, pd.DataFrame],
                  tracks: List[str] = None,
                  normalize         = True) -> pd.DataFrame:
        "The dataframe used for the displays"
        beadqc = data if isinstance(data, pd.DataFrame) else beadqualitysummary(data)
        frame  = mostcommonerror(beadqc).fillna(self.params[0]).reset_index()
        value  = self.value(normalize)

        disc   = pd.crosstab(frame.track, frame.mostcommonerror,
                             normalize = 'index' if normalize else False)
        if normalize:
            disc *= 100
        if tracks:
            disc = disc.loc[tracks]
        disc.reset_index(inplace = True)
        disc = (disc
                .melt(id_vars = ['track'])
                .rename(columns = {'mostcommonerror': 'error', 'value': value}))

        disc.set_index('track', inplace = True)
        disc = disc.join(frame.groupby('track').bead.count().rename('beads'))
        disc.reset_index(inplace = True)
        disc[value]  *= np.where(disc.error == self.params[0], 1, -1)
        disc['error'] = disc['error'].astype('category')

        disc.set_index("error", inplace = True)
        disc = disc.loc[list(self.params)+list(set(disc.index)-set(self.params)),:]
        disc.reset_index(inplace = True)
        return disc

    def display(self, trackqc: TrackQC,
                tracks: List[str] = None,
                normalize         = True) -> hv.Layout:
        """
        Outputs a heatmap. Columns are types of Error and rows are tracks. Each
        cell presents the percentage of appearance of the specific error at the
        specific track.
        """
        disc   = self.dataframe(trackqc, tracks, normalize)
        value  = self.value(normalize)
        nbeads = len(trackqc.status.index)
        hmap   = (
            hv.HeatMap(
                disc[~disc['error'].isna()],
                kdims = ['error', 'track'],
                vdims = [value, 'beads']
            )
            .redim.range(**{value: (-100, 100) if normalize else (-nbeads, nbeads)})
            .redim.label(error = " ")
            .options(**self.styleopts)
        )

        fmt = (lambda x: f'{abs(x):.01f}') if normalize else (lambda x: f'{abs(x):.1f}')
        return ((hmap*hv.Labels(hmap).redim.value_format(**{value: fmt}))
                .clone(label = self.title))

def displaytrackstatus(data: Union[TrackQC, pd.DataFrame],
                       tracks: List[str] = None,
                       normalize         = True, **kwa) -> hv.Layout:
    """
    Outputs a heatmap. Columns are types of Error and rows are tracks. Each
    cell presents the percentage of appearance of the specific error at the
    specific track.
    """
    return TrackStatus(**kwa).display(data, tracks, normalize)

__all__ = ['displaytrackstatus']
