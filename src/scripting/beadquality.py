#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   itertools import product
from   typing    import NamedTuple, Union, cast

import holoviews as hv
import pandas    as pd
import numpy     as np

from   data.__scripting__.track      import Track
from   data.__scripting__.tracksdict import TracksDict

class TrackQC(NamedTuple): # pylint: disable=missing-docstring
    table:  pd.DataFrame
    status: pd.DataFrame

def chronologicalorder(tracks: TracksDict):
    "return tracks in chronological order"
    return tracks.dataframe().key.values

def modificationdate(tracks: TracksDict):
    "return tracks in chronological order"
    frame = tracks.dataframe().rename(columns = dict(key = 'track'))
    frame.set_index('key', inplace = True)
    return frame.modification

def trackqualitysummary(tracks: TracksDict, dfmsg: pd.DataFrame = None) -> TrackQC:
    """
    Outputs:

    * status:   dataframe with the status of bead per track. Either missing,
                fixed or NaN of it is neither missing nor fixed
    * table:    dataframe with a resume of fixed, missing and not fixed/missing
    """
    if dfmsg is None:
        dfmsg = getattr(tracks, 'cleaning').messages()
        dfmsg.reset_index(inplace = True)
    elif not isinstance(dfmsg, pd.RangeIndex):
        dfmsg = dfmsg.reset_index()

    order = list(chronologicalorder(tracks))
    print(order)
    dfmsg = dfmsg.assign(trackorder = [order.index(key) for key in dfmsg['key']],
                         pc_cycles  = dfmsg.cycles*100/[cast(Track, tracks[i]).ncycles 
                                                        for i in dfmsg.key])

    dfstatus = pd.DataFrame(columns = pd.Series(order), index = tracks.availablebeads())

    def _fill(label, tpe, cycs, msg = None):
        tmp = dfmsg[dfmsg['types']==tpe][lambda x: x.pc_cycles > cycs]
        if msg:
            tmp = tmp[tmp['message'].str.find(msg)!=-1]
        for pair in tmp.groupby(['bead', 'trackorder']).count().index:
            dfstatus.iloc[pair] = label

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
    return TrackQC(dfstatus.fillna('ok').apply(pd.value_counts).T, dfstatus)

def beadqualitysummary(tracks:TracksDict,
                       messages: pd.DataFrame,
                       status:   pd.DataFrame) -> pd.DataFrame:
    """
    a dataframe of frequence of errors per bead per track.  The line bd/trk has
    as many columns as the nb of types of errors that can be detected for a
    bead.  If the bead is missing/fixed all errors are set to NaN
    """
    frame = (messages
             .reset_index()
             .rename(columns = {'key': 'track'})
             .assign(keys = lambda x: x.types+x.messages)
             .assign(keys = lambda x: x.keys.apply(lambda y: y.replace(' ', ''))))

    items = set(product(tracks.availablebeads(), tracks))
    ind   = (pd.MultiIndex.from_tuples(items - set(messages[['bead', 'key']].values))
             .set_names(['track', 'bead']))

    good  = frame.groupby(['bead', 'track', 'keys']).cycles.first()
    good.reset_index(inplace = True)
    good  = good.pivot_table(index   = ['track', 'bead'],
                             columns = ['keys'],
                             values  = ['cycles'],
                             aggfunc = np.mean)
    good.reset_index(inplace = True)
    good  = pd.concat([good, pd.DataFrame(columns = frame.keys.values, index = ind)])

    good.set_index(['track', 'bead'], inplace = True)
    good  = (good.join(modificationdate(tracks))
             .assign(status = [status[i][j] for i, j in iter(good.index)])
             .assign(status = status.apply(lambda x: x if x in ('missing', 'fixed') else '')))

    # remove errors corresponding to missing beads
    good.reset_index(inplace = True)
    good.set_index(['bead', 'track', 'status'], inplace = True)
    good.loc[(slice(None), slice(None), 'missing'), :] = np.NaN

    # remove errors corresponding to fixed beads
    extent = next(i for i in good.columns if 'extent' in i and '<' in i)
    good.loc[(slice(None), slice(None), 'fixed'), extent] = np.NaN

    good.reset_index(inplace = True)
    return good

def bestbeadorder(beadqc: pd.DataFrame) -> pd.Series:
    """
    Outputs the list of beads sorted by best to worst
    in terms of the errors the bead presents
    """
    ncycs = beadqc.max().max()
    frame = beadqc.copy()
    frame = frame.assign(status = frame.status.apply(lambda x: ncycs if len(x) else 0))
    frame.set_index(['bead', 'track', 'modification'], inplace = True)

    frame = frame.sum(axis = 1)
    frame.sort_values(inplace = True)
    frame.reset_index(inplace = True)
    return frame.bead

def _addstatuscols(beadqc: pd.DataFrame,
                   fixedassingleerror = True,
                   states             = ('missing', 'fixed', '')) -> pd.DataFrame:
    "add a column per status"
    if states == 'bad':
        states = ('missing', 'fixed')

    if fixedassingleerror:
        beadqc = beadqc.copy().set_index(['bead', 'track', 'status'])
        beadqc.loc[(slice(None), slice(None), 'fixed'), :] = np.NaN
        beadqc.reset_index(inplace = True)

    ncycs = beadqc.max().max()
    def _get(label):
        return beadqc.status.apply(lambda x: (ncycs if x == label else 0))
    frame = beadqc.copy().assign(**{i if i else 'noerror': _get(i) for i in states})
    del frame['status']
    return frame

def mostcommonerror(beadqc: pd.DataFrame,
                    fixedassingleerror = True,
                    states             = ('missing', 'fixed', '')) -> pd.DataFrame:
    """
    outputs a dataframe columns are the tracks rows the beads,
    each cell contains the status of the bead: noError, extent>0.5,...
    """
    return (_addstatuscols(beadqc, states = states, fixedassingleerror = fixedassingleerror)
            .set_index(['bead','track', 'modification'])
            .idxmax(axis = 1)
            .rename('mostcommonerror'))

def displaystatusevolution(trackqc: Union[pd.DataFrame, TrackQC],
                           tracks:  TracksDict)->hv.Overlay:
    "Scatter plot showing the evolution of the nb of missing, fixed and no-errors beads."
    frame    = (trackqc.table if isinstance(trackqc, TrackQC) else trackqc).T
    trkdates = ['d{0}-{1}h{2}m'.format(d.day,d.hour,d.minute)
                for d in pd.DatetimeIndex(modificationdate(tracks).values)]

    lst   = 'fixed', 'missing', 'ok'
    total = sum(next(iter(frame.loc[i])) for i in lst)
    get   = lambda x: (x, np.array(list(frame.loc[x]))/total)
    frame = pd.DataFrame({"date": trkdates, **dict(get(i) for i in lst)})
    pts   = [hv.Points(frame, 'date', i, label = i) for i in lst]
    crvs  = [hv.Curve (frame, 'date', i, group = i) for i in lst]
    crvs[-1] = crvs[-1].clone(vdims = ['nb']).opts(plot = dict(xrotation = 45))
    return (hv.Overlay(pts + crvs)
            .redim.range(y = (0,100))
            .redim.label(x ='date', y = f'% beads (total {int(total*100)})'))

def displaytrackstatus(beadqc:pd.DataFrame,
                       ordertracks = None,
                       normalize   = True) -> hv.Layout:
    """
    Outputs 2 heatmaps side to side. Columns are types of Error and rows are
    tracks. Each cell presents the percentage of appearance of the specific
    error at the specific track.
    """
    value  = 'percentage' if normalize else 'count'
    frame  = mostcommonerror(beadqc).fillna("ok").reset_index()

    disc   = pd.crosstab(frame.track, frame.mostcommonerror,
                         normalize = 'index' if normalize else False)
    if normalize:
        disc *= 100
    if ordertracks:
        disc = disc.loc[ordertracks]
    disc.reset_index(inplace = True)
    disc = (disc
            .melt(id_vars = ['track'], variable = list(set(disc.columns) - {'track'}))
            .rename(columns = {'variable': 'error', 'value': value})
            .assign(ok    = lambda x: np.where(x.error == 'ok', 'ok',    np.NaN))
            .assign(error = lambda x: np.where(x.error != 'ok', x.error, np.NaN)))

    disc.set_index('track', inplace = True)
    disc = disc.join(pd.Series(frame.groupby('track').bead.count()).rename('beads'))
    disc.reset_index(inplace = True)

    nbeads = len(frame.bead.unique())
    def _labels(xaxis, color):
        hmap = (hv.HeatMap(disc, kdims = [xaxis, 'track'], vdims = [value, 'beads'])
                .redim.range(**{xaxis: (0, 100 if normalize else nbeads)})
                .redim.label(**{xaxis: ""})
                .options(dict(tools     = ['hover'],
                              cmap      = color,
                              xrotation = 40,
                              color_bar = True)))

        fmt   = {value: ((lambda x: '.01f' % x) if normalize else (lambda x: '.1f' % x))}
        return hmap*hv.Labels(hmap).redim.value_format(**fmt)
    return _labels('ok', 'Blues')+_labels('error', 'Reds')

def displaybeadandtrackstatus(beadqc: pd.DataFrame,
                              ordertracks = None,
                              orderbeads  = None) -> hv.Overlay:
    "Outputs heatmap with the status of the beads per track"
    if orderbeads is None:
        orderbeads = sorted(beadqc.bead.unique())
    if ordertracks is None:
        ordertracks = sorted(beadqc.track.unique())

    frame   = mostcommonerror(beadqc).fillna("").sort_values(['bead', 'track'])
    errlist = sorted(frame.mostcommonerror.unique())
    errlist.remove("")
    errint  = {"":-1., **{j: i/len(errlist) for i, j in enumerate(errlist)}}
    frame   = frame.assign(errorid = frame.mostcommonerror.apply(errint.__getitem__))
    return (hv.HeatMap(frame,
                       kdims = ['bead', 'track'],
                       vdims = ['errorid', 'mostcommonerror'])
            .options(dict(tools     = ['hover'],
                          yrotation = 40,
                          color_bar = True))
            *hv.Labels(frame, kdims = ['bead', 'track'], vdims = ['mostcommonerror']))

def flowBeads(beadqc: pd.DataFrame, tracks):
    """
    outputs a flow diagram between two tracks showing the proportion
    of the beads classified by their status (their mostCommonError)
    """
    col = (mostcommonerror(beadqc)
           .replace(list(set(col.unique()) - {'fixed', 'missing', 'ok'}), 'error')
           .reset_index())
    col.sort_values('modification', inplace = True)

    if tracks is None:
        tracks = col.track.values[[0,-1]]

    errors = col.pivot(index = 'bead', columns = 'track', value = 'mostcommonerror')
    errors.reset_index(inplace = True)
    errors = errors.rename(columns = {'index': 'nodenumber'})

    nodes  = col.groupby(['track', 'modification', 'mostcommonerror']).bead.count()
    nodes.reset_index(inplace = True)
    nodes.sort_values(['modification', 'mostcommonerror'], inplace = True)
    nodes.reset_index(inplace = True) # add an 'index' column
    nodes.set_index(['track', 'mostcommonerror'], inplace = True)

    edges  = pd.DataFrame(columns = ['From', 'To', 'bead'])
    for i in range(len(tracks)-1):
        tmp = errors.groupby(list(tracks[i:i+1])).bead.count()
        tmp.reset_index(inplace = True)
        tmp = tmp.rename(columns = {tracks[i]: 'From', tracks[i+1]: 'To'})
        for j, k in zip(('From', 'To'), tracks[i:i+1]):
            tmp[j] = [nodes.loc[k, l].nodenumber.values[0] for l in tmp[j]]

        edges = pd.concatenate([edges, tmp])

    hvnodes = hv.Dataset(nodes, vdims = list(set(nodes.columns) - {'nodenumber'}))
    return (hv.Sankey((edges, hvnodes), ['From', 'To'], ['bead'])
            .options(label_index = 'mostcommonerror', edge_color_index = 'From'))
