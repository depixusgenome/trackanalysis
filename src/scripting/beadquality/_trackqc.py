#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   itertools import product
from   typing    import NamedTuple, cast

import holoviews as hv
import pandas    as pd
import numpy     as np

from   utils.holoviewing             import displayhook as _displayhook
from   data.__scripting__.track      import Track
from   data.__scripting__.tracksdict import TracksDict

@_displayhook(lambda x: hv.Table(x[0])+hv.Table(x[1])) # pylint: disable=missing-docstring
class TrackQC(NamedTuple):
    table:    pd.DataFrame
    status:   pd.DataFrame
    messages: pd.DataFrame

def trackqualitysummary(tracks: TracksDict, dfmsg: pd.DataFrame = None) -> TrackQC:
    """
    Outputs:

    * status:   dataframe with the status of bead per track. Either missing,
                fixed or NaN of it is neither missing nor fixed
    * table:    dataframe with a summary of fixed, missing and not fixed/missing
    """
    if dfmsg is None:
        dfmsg = getattr(tracks, 'cleaning').dataframe()
    if not isinstance(dfmsg.index, pd.RangeIndex):
        dfmsg = dfmsg.reset_index()
    dfmsg              = dfmsg.rename(columns = {'key': 'track'})
    dfmsg['pc_cycles'] = dfmsg.cycles*100/[cast(Track, tracks[i]).ncycles for i in dfmsg.track]

    dfstatus = pd.DataFrame(columns = pd.Series(tracks.dataframe().key.values),
                            index   = pd.Int64Index(tracks.availablebeads(), name = 'bead'))

    order = dict(dfmsg[['modification', 'track']].values)
    def _fill(label, tpe, cycs, msg = None):
        tmp   = dfmsg[dfmsg['types']==tpe][lambda x: x.pc_cycles > cycs]
        if msg:
            tmp = tmp[tmp['message'].str.find(msg)!=-1]
        for bead, trk in tmp.groupby(['bead', 'modification']).count().index:
            dfstatus.loc[bead, order[trk]] = label

    _fill('missing', 'hfsigma',  99)  # hfsigma too low
    _fill('missing', 'pingpong', 10) # ping pong appears

    #if there is a good track after missing tracks,
    #then the previous tracks are not missing
    for bead, vals in dfstatus.iterrows():
        ind = next((i for i, j in enumerate(pd.isnull(vals)[::-1]) if j), None)
        if ind is not None:
            dfstatus.iloc[bead, 0:len(vals)-ind] = np.NaN

    #if extent is too small, the bead is fixed, not missing
    _fill('fixed', 'extent', 99, '<')

    dfsumm = (dfstatus
              .fillna('ok').apply(pd.value_counts).T
              .join(dfmsg[['track', 'modification']]
                    .groupby("track").modification.first()))
    dfsumm.index.set_names("track", inplace = True)
    dfsumm['cyclecount'] = [tracks[i].ncycles for i in dfsumm.index]

    # recompute summary, adding errors
    return _adderrors(TrackQC(dfsumm, dfstatus, dfmsg))

def beadqualitysummary(trackqc: TrackQC) -> pd.DataFrame:
    """
    a dataframe of frequence of errors per bead per track.  The line bd/trk has
    as many columns as the nb of types of errors that can be detected for a
    bead.  If the bead is missing/fixed all errors are set to NaN
    """
    frame = trackqc.messages.copy()
    frame['longmessage'] = (frame.types+frame.message).apply(lambda x: x.replace(" ", ""))
    cols   = frame.longmessage.unique()

    frame = frame.pivot_table(index   = ['bead', 'track'],
                              columns = 'longmessage',
                              values  = 'cycles')

    frame['status'] = [trackqc.status[j][i] for i, j in iter(frame.index)]
    frame['status'] = frame.status.apply(lambda x: x if x in ('missing', 'fixed') else np.NaN)

    # remove errors corresponding to fixed beads
    extent = next(i for i in cols if 'extent' in i and '<' in i)
    frame.loc[frame.status == 'fixed', extent] = np.NaN

    # remove errors corresponding to missing beads
    frame.loc[frame.status == 'fixed', list(set(frame.columns) - {'status'})] = np.NaN

    ind   = pd.MultiIndex.from_tuples(set(product(trackqc.status.index, trackqc.status.columns))
                                      .difference(frame.index))
    frame = (pd.concat([frame, pd.DataFrame(columns = frame.columns, index = ind)])
             .join(trackqc.table[['modification', 'cyclecount']]))
    for i in cols:
        frame[i] *= 1e2/frame.cyclecount

    frame.reset_index(inplace = True)
    return frame

def mostcommonerror(beadqc: pd.DataFrame,
                    fixedassingleerror = True) -> pd.DataFrame:
    """
    outputs a dataframe columns are the tracks rows the beads,
    each cell contains the status of the bead: noError, extent>0.5,...
    """
    frame = beadqc.assign(status = beadqc.status.fillna("noerror"))
    if fixedassingleerror:
        cols   = [i for i in frame.columns if '>' in i or '<' in i]
        frame.loc[frame.status == 'fixed', cols] = np.NaN

    newcols = frame.pivot_table(index   = ["bead", 'track'],
                                columns = "status",
                                values  = 'cyclecount')
    frame.set_index(['bead', 'track'], inplace = True)
    frame  = frame.join(newcols)

    frame.set_index(['modification'], inplace = True, append = True)
    for i in ('status', 'cyclecount', 'noerror'):
        del frame[i]

    return frame.idxmax(axis = 1).rename('mostcommonerror')

def _adderrors(qcdf):
    col = mostcommonerror(beadqualitysummary(qcdf))
    col = col.replace(list(set(col.unique()) - {'fixed', 'missing', np.NaN}), 'error')
    col = col.fillna('ok')
    col = col.astype('category')

    frame = col.reset_index()
    frame = frame.groupby(["track",  "mostcommonerror"]).bead.count()
    frame.reset_index(inplace = True)

    frame = pd.pivot_table(frame, values = 'bead', columns = 'mostcommonerror', index = 'track')
    # pylint: disable=not-an-iterable
    setattr(frame, 'columns', [i for i in getattr(frame, 'columns')])

    mods  = qcdf.messages.groupby("track").agg({'modification': 'first'})
    frame = frame.join(mods)
    frame.sort_values('modification', inplace = True)
    return TrackQC(frame, qcdf.status, qcdf.messages)

__all__ = ['TrackQC', 'beadqualitysummary', 'trackqualitysummary', 'mostcommonerror']
