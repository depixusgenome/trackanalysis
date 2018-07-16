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
from   bokeh.models                  import HoverTool, FactorRange, CategoricalAxis

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
    * table:    dataframe with a resume of fixed, missing and not fixed/missing
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
    return TrackQC(dfsumm, dfstatus, dfmsg)

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

def displaystatusevolution(trackqc: Union[pd.DataFrame, TrackQC])->hv.Overlay:
    "Scatter plot showing the evolution of the nb of missing, fixed and no-errors beads."
    frame         = trackqc.table.reset_index()
    frame['date'] = frame.modification.apply(lambda d: f'd{d.day}-{d.hour}h{d.minute}m')


    total = len(trackqc.status.index)
    lst    = 'ok', 'fixed', 'missing'
    colors = 'blue', 'orange', 'red'
    for i in lst:
        frame[i] *= 100/total
    hover = HoverTool(tooltips=[("(date, track)", "(@date, @track)"),
                                *((f"# {i}", f"@{i}") for i in lst),
                                ("# cycles", "@cyclecount")])
    crvs   = [(hv.Points(frame, kdims = ['date', i], label = i)
               (style = dict(color = j, marker = 'o', size = 5),
                plot  = dict(tools=[hover], show_grid=True)))
              for i, j in zip(lst, colors)]
    crvs  += [(hv.Curve (frame, kdims = ['date', i], label = i)
               (style = dict(color = j),
                plot  = dict(tools=[hover], show_grid=True)))
              for i, j in zip(lst, colors)]

    def apply_formatter(plot, element):
        plot.state.extra_x_ranges = {"track": FactorRange(*frame.track.values)}
        plot.state.add_layout(CategoricalAxis(x_range_name="track"), 'above')

    return (hv.Overlay(crvs)
            .redim.range(y = (0,100))
            .redim.label(x ='date', ok = f'% beads (total {int(total)})')
            .options(xrotation = 45, finalize_hooks=[apply_formatter])
            .clone(label="Evolution of the bead status as function of time")
           )

def displaytrackstatus(data: Union[TrackQC, pd.DataFrame],
                       ordertracks = None,
                       normalize   = True) -> hv.Layout:
    """
    Outputs a heatmap. Columns are types of Error and rows are tracks. Each
    cell presents the percentage of appearance of the specific error at the
    specific track.
    """
    beadqc = data if isinstance(data, pd.DataFrame) else beadqualitysummary(data)
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
            .melt(id_vars = ['track'])
            .rename(columns = {'mostcommonerror': 'error', 'value': value}))

    disc.set_index('track', inplace = True)
    disc = disc.join(pd.Series(frame.groupby('track').bead.count()).rename('beads'))
    disc.reset_index(inplace = True)
    disc[value] *= np.where(disc.error == 'ok', 1, -1)
    disc['error'] = disc['error'].astype('category')
    disc.set_index("error", inplace = True)
    order  = ['ok', 'fixed', 'missing']
    order += sorted(set(disc.index).difference(order))
    disc = disc.loc[order,:]
    disc.reset_index(inplace = True)

    nbeads = len(frame.bead.unique())
    hmap   = (hv.HeatMap(disc[~disc['error'].isna()],
                         kdims = ['error', 'track'],
                         vdims = [value, 'beads'])
              .redim.range(**{value: (-100, 100) if normalize else (-nbeads, nbeads)})
              .redim.label(**{'error': " "})
              (plot  = dict(tools     = ['hover'],
                            xrotation = 40,
                            colorbar  = True),
               style = dict(cmap      = 'RdYlGn')))

    fmt = (lambda x: f'{abs(x):.01f}') if normalize else (lambda x: f'{abs(x):.1f}')
    return ((hmap*hv.Labels(hmap).redim.value_format(**{value: fmt}))
            .clone(label = 'By track, the percentage of beads per status & error'))

def displaybeadandtrackstatus(data: Union[TrackQC, pd.DataFrame],
                              ordertracks = None,
                              orderbeads  = None) -> hv.HeatMap:
    "Outputs heatmap with the status of the beads per track"
    beadqc = data if isinstance(data, pd.DataFrame) else beadqualitysummary(data)
    if orderbeads is None:
        orderbeads = sorted(beadqc.bead.unique())
    if ordertracks is None:
        ordertracks = sorted(beadqc.track.unique())

    frame   = mostcommonerror(beadqc).fillna("").reset_index()
    errlist = sorted(frame.mostcommonerror.unique())
    errlist.remove("")
    errint  = {"":1., **{j: -i/len(errlist) for i, j in enumerate(errlist)}}
    frame   = frame.assign(errorid = frame.mostcommonerror.apply(errint.__getitem__))
    return (hv.HeatMap(frame,
                       kdims = ['bead', 'track'],
                       vdims = ['errorid', 'mostcommonerror'])
            (plot  = dict(tools     = ['hover'],
                          xrotation = 40,
                          colorbar  = True),
             style = dict(cmap      = 'RdYlGn'))
            .clone(label = "Most common error per track and bead"))

def displaybeadflow(trackqc: TrackQC, tracks = None):
    """
    outputs a flow diagram between two tracks showing the proportion
    of the beads classified by their status (their mostCommonError)
    """
    col    = mostcommonerror(beadqualitysummary(trackqc))
    frame  = (col.replace(list(set(col.unique()) - {'fixed', 'missing', np.NaN}), 'error')
              .reset_index()
              .fillna("ok"))
    frame.sort_values('modification', inplace = True)

    if tracks is None:
        tracks = trackqc.status.columns[0], trackqc.status.columns[-1]
    elif tracks is all or tracks is Ellipsis:
        tracks = trackqc.status.columns

    errors = frame.pivot(index = 'bead', columns = 'track', values = 'mostcommonerror')
    errors.reset_index(inplace = True)

    nodes  = (frame.groupby(['track', 'modification', 'mostcommonerror']).bead.count()
              .reset_index(["modification", "mostcommonerror"])
              .loc[list(tracks), :])
    nodes.reset_index(inplace = True)
    nodes.sort_values(['modification', 'mostcommonerror'], inplace = True)
    nodes.reset_index(inplace = True) # add an 'index' column
    nodes = nodes.rename(columns = {'index': 'nodenumber'})
    nodes.set_index(['track', 'mostcommonerror'], inplace = True)

    edges  = pd.DataFrame(columns = ['From', 'To', 'bead'])
    for i in range(len(tracks)-1):
        tmp = (errors.groupby(list(tracks[i:i+2])).bead.count()
               .reset_index())
        for j, k in zip(('From', 'To'), tracks[i:i+2]):
            tmp[j] = [nodes.loc[k, l].nodenumber for l in tmp[k]]
        tmp   = tmp.rename(columns = {tracks[i]: 'Left', tracks[i+1]: 'Right'})
        edges = pd.concat([edges, tmp])

    nodes.reset_index(inplace = True)
    hvnodes = hv.Dataset(nodes, "nodenumber")
    return (hv.Sankey((edges, hvnodes), ['From', 'To'], ['bead', 'Left'])
            .options(label_index = 'mostcommonerror',
                     edge_color_index = 'Left',
                     color_index = 'mostcommonerror'))
