#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Provides displays on good and bad beads
"""
import pandas                   as     pd

from   scripting.holoviewing    import hv, addto
from   .                        import TrackCleaningScript, TracksDictCleaningScript

@addto(TrackCleaningScript)
def display(self):
    "returns a table of cleaning messages"
    return self.messages()

@addto(TracksDictCleaningScript)                     # type: ignore
def display(self, sort = 'nbadkeys') -> hv.HeatMap: # pylint: disable=function-redefined
    """
    returns a heat map display good and bad beads per track

    Options:

    * `sort` Є {"nbadkeys", "nbadbeads"} indicates whether to sort by bad
    beads or bad tracks
    """
    frame = self.messages()

    fcn   = lambda i: ''.join(f"{j.types}: {j.cycles} {j.message}\n"
                              for j in i.itertuples())
    vdims = ["nbadkeys", "nbadbeads"]
    if sort  == 'nbadkeys':
        vdims = vdims[::-1]

    new   = pd.DataFrame({'msg': frame.groupby(['bead', 'key']).apply(fcn)})
    fcn   = lambda x, y: (new
                          .groupby(level = x)
                          .apply(len)
                          .rename(f'nbad{y}s'))
    grp   = (new
             .join(fcn('bead', 'key'))
             .join(fcn('key',  'bead'))
             .groupby(['bead', 'key'])
             .aggregate(dict(nbadkeys = 'min', nbadbeads = 'min', msg = 'sum'))
             .reset_index()
             .sort_values(vdims))
    return (hv.HeatMap(grp, kdims = ['bead', 'key'], vdims = vdims + ['msg'])
            (plot = dict(tools=['hover'])))
