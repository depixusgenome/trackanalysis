#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   itertools import product
from   typing    import NamedTuple, Union, List, cast

import holoviews as hv
import pandas    as pd
import numpy     as np
from   bokeh.models                  import HoverTool, FactorRange, CategoricalAxis

from   utils                         import initdefaults
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

class StatusEvolution:
    """
    Display the evolution of beads in the 3 categories: 'ok', 'fixed' and 'missing'.
    """
    params    = 'ok', 'fixed', 'missing'
    colors    = 'blue', 'orange', 'red'
    tooltips  = [("(date, track)", "(@date, @track)"),
                 *((f"# {i}", f"@{i}") for i in params),
                 ("# cycles", "@cyclecount")]
    xlabel    = 'date'
    ylabel    = '% beads (total {total})'
    title     = "Evolution of the bead status as function of time"
    ptsstyle  = dict(marker = 'o', size = 5)
    plotopts  = {'show_grid': True, 'xrotation': 45}

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    @staticmethod
    def dataframe(trackqc: Union[pd.DataFrame, TrackQC]) -> hv.Overlay:
        "The dataframe used for the displays"
        frame         = trackqc.table.reset_index()
        frame['date'] = frame.modification.apply(lambda d: f'd{d.day}-{d.hour}h{d.minute}m')
        return frame

    def display(self, trackqc: Union[pd.DataFrame, TrackQC])->hv.Overlay:
        "Scatter plot showing the evolution of the nb of missing, fixed and no-errors beads."
        frame = self.dataframe(trackqc)
        total = len(trackqc.status.index)
        for i in self.params:
            frame[i] *= 100/total
        hover = HoverTool(tooltips = self.tooltips)
        crvs  = [(hv.Points(frame, kdims = ['date', i], label = i)
                  (style = dict(color = j, **self.ptsstyle),
                   plot  = dict(tools=[hover], **self.plotopts)))
                 for i, j in zip(self.params, self.colors)]
        crvs += [(hv.Curve (frame, kdims = ['date', i], label = i)
                  (style = dict(color = j),
                   plot  = dict(tools=[hover], **self.plotopts)))
                 for i, j in zip(self.params, self.colors)]

        def _newaxis(plot, _):
            plot.state.extra_x_ranges = {"track": FactorRange(*frame.track.values)}
            plot.state.add_layout(CategoricalAxis(x_range_name="track"), 'above')

        return (hv.Overlay(crvs)
                .redim.range(y = (0,100))
                .redim.label(x = self.xlabel, ok = self.ylabel.format(total = int(total)))
                .options(finalize_hooks=[_newaxis])
                .clone(label=self.title)
               )

class TrackStatus:
    """
    Outputs a heatmap. Columns are types of Error and rows are tracks. Each
    cell presents the percentage of appearance of the specific error at the
    specific track.
    """
    params = 'ok', 'fixed', 'missing'
    styleopts = dict(cmap  = 'RdYlGn')
    plotopts  = dict(tools = ['hover'], xrotation = 40, colorbar  = True)
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
        hmap   = (hv.HeatMap(disc[~disc['error'].isna()],
                             kdims = ['error', 'track'],
                             vdims = [value, 'beads'])
                  .redim.range(**{value: (-100, 100) if normalize else (-nbeads, nbeads)})
                  .redim.label(**{'error': " "})
                  (plot  = self.plotopts, style = self.styleopts))

        fmt = (lambda x: f'{abs(x):.01f}') if normalize else (lambda x: f'{abs(x):.1f}')
        return ((hmap*hv.Labels(hmap).redim.value_format(**{value: fmt}))
                .clone(label = self.title))

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

def displaystatusevolution(trackqc: Union[pd.DataFrame, TrackQC], **kwa)->hv.Overlay:
    "Scatter plot showing the evolution of the nb of missing, fixed and no-errors beads."
    return StatusEvolution(**kwa).display(trackqc)

def displaystatusflow(trackqc: TrackQC, tracks: List[str] = None):
    """
    outputs a flow diagram between two tracks showing the proportion
    of the beads classified by their status (their mostCommonError)
    """
    return StatusFlow.display(trackqc, tracks)

def displaytrackstatus(data: Union[TrackQC, pd.DataFrame],
                       tracks: List[str] = None,
                       normalize         = True, **kwa) -> hv.Layout:
    """
    Outputs a heatmap. Columns are types of Error and rows are tracks. Each
    cell presents the percentage of appearance of the specific error at the
    specific track.
    """
    return TrackStatus(**kwa).display(data, tracks, normalize)

def displaybeadandtrackstatus(data: Union[TrackQC, pd.DataFrame],
                              tracks: List[str] = None,
                              beads:  List[int] = None, **kwa) -> hv.HeatMap:
    "Outputs heatmap with the status of the beads per track"
    return BeadTrackStatus(**kwa).display(data, tracks, beads)
