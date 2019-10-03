#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Means for creating and displaying the quality of a set of tracks
"""

from   itertools import product
from   typing    import cast

import pandas    as pd
import numpy     as np

from   data.__scripting__.track      import Track
from   data.__scripting__.tracksdict import TracksDict
from   utils                         import initdefaults

class TrackQC:
    """
    Outputs:

    * status:   dataframe with the status of bead per track. Either missing,
                fixed or NaN of it is neither missing nor fixed
    * table:    dataframe with a summary of fixed, missing and not fixed/missing
    """
    table:    pd.DataFrame
    status:   pd.DataFrame
    messages: pd.DataFrame

    missinghfsigma    = 90
    missingpopulation = 90
    missingpingpong   = 10
    fixedextent       = 99
    @initdefaults(locals())
    def __init__(self, **_):
        pass

    def __messages(self, tracks, dfmsg):
        if dfmsg is None:
            dfmsg = getattr(tracks, 'cleaning').dataframe()
        if not isinstance(dfmsg.index, pd.RangeIndex):
            dfmsg = dfmsg.reset_index()
        self.messages = dfmsg.rename(columns = {'key': 'track'})
        cycs          = [cast(Track, tracks[i]).ncycles for i in self.messages.track]
        self.messages['pc_cycles'] = self.messages.cycles*100/cycs

    def __status(self, tracks):
        self.status = pd.DataFrame(columns = pd.Series(tracks.dataframe().key.values),
                                   index   = pd.Int64Index(tracks.availablebeads(),
                                                           name = 'bead'))

        order = dict(self.messages[['modification', 'track']].values)
        def _fill(label, tpe, cycs, msg = None):
            tmp   = self.messages[self.messages['types']==tpe][lambda x: x.pc_cycles > cycs]
            if msg:
                tmp = tmp[tmp['message'].str.find(msg)!=-1]
            for bead, trk in tmp.groupby(['bead', 'modification']).count().index:
                self.status.loc[bead, order[trk]] = label

        _fill('missing', 'hfsigma',     self.missinghfsigma)
        _fill('missing', 'population',  self.missingpopulation)
        _fill('missing', 'pingpong',    self.missingpingpong)

        #if there is a good track after missing tracks,
        #then the previous tracks are not missing
        columns = list(self.status.columns)
        for bead, vals in self.status.iterrows():
            ind = next((i for i, j in enumerate(pd.isnull(vals)[::-1]) if j), None)
            if ind is not None:
                self.status.loc[bead, columns[-1:len(vals)-ind]] = np.NaN

        #if extent is too small, the bead is fixed, not missing
        _fill('fixed', 'extent', self.fixedextent, '<')

    def __table(self, tracks):
        self.table = (self.status
                      .fillna('ok').apply(pd.value_counts).T
                      .join(self.messages[['track', 'modification']]
                            .groupby("track").modification.first()))
        self.table.index.set_names("track", inplace = True)
        self.table['cyclecount'] = [tracks[i].ncycles for i in self.table.index]

        col = mostcommonerror(self.beadqualitysummary())
        col = col.replace(list(set(col.unique()) - {'fixed', 'missing', np.NaN}), 'error')
        col = col.fillna('ok')
        col = col.astype('category')

        frame = col.reset_index()
        frame = frame.groupby(["track",  "mostcommonerror"]).bead.count().reset_index()

        frame = pd.pivot_table(frame, values = 'bead', columns = 'mostcommonerror', index = 'track')
        # pylint: disable=not-an-iterable
        setattr(frame, 'columns', list(getattr(frame, 'columns')))

        self.table = frame.join(self.table[list(set(self.table.columns)-set(frame.columns))])
        self.table.sort_values('modification', inplace = True)
        return self

    def trackqualitysummary(self,
                            tracks: TracksDict,
                            dfmsg:  pd.DataFrame = None) -> 'TrackQC':
        """
        Outputs:

        * status:   dataframe with the status of bead per track. Either missing,
                    fixed or NaN of it is neither missing nor fixed
        * table:    dataframe with a summary of fixed, missing and not fixed/missing
        """

        self.__messages(tracks, dfmsg)
        self.__status(tracks)
        self.__table(tracks)
        return self

    def beadqualitysummary(self) -> pd.DataFrame:
        """
        a dataframe of frequence of errors per bead per track.  The line bd/trk has
        as many columns as the nb of types of errors that can be detected for a
        bead.  If the bead is missing/fixed all errors are set to NaN
        """
        frame = self.messages.copy()
        frame['longmessage'] = (frame.types+frame.message).apply(lambda x: x.replace(" ", ""))
        cols   = frame.longmessage.unique()

        frame = frame.pivot_table(index   = ['bead', 'track'],
                                  columns = 'longmessage',
                                  values  = 'cycles')

        frame['status'] = [self.status[j][i] for i, j in iter(frame.index)]
        fixed           = frame.status.apply(lambda x: x in ('missing', 'fixed'))
        frame['status'] = frame.status.apply(lambda x: x if x in ('missing', 'fixed') else np.NaN)

        # remove errors corresponding to fixed beads
        extent = next((i for i in cols if 'extent' in i and '<' in i), None)
        if extent:
            frame.loc[fixed, extent] = np.NaN

        # remove errors corresponding to missing beads
        frame.loc[fixed, list(set(frame.columns) - {'status'})] = np.NaN

        ind   = pd.MultiIndex.from_tuples(set(product(self.status.index, self.status.columns))
                                          .difference(frame.index))
        frame = (pd.concat([frame, pd.DataFrame(columns = frame.columns, index = ind)])
                 .join(self.table[['modification', 'cyclecount']]))
        for i in cols:
            frame[i] *= 1e2/frame.cyclecount

        frame.reset_index(inplace = True)
        return frame

def trackqualitysummary(tracks: TracksDict,
                        dfmsg:  pd.DataFrame = None,
                        **kwa) -> TrackQC:
    """
    Outputs:

    * status:   dataframe with the status of bead per track. Either missing,
                fixed or NaN of it is neither missing nor fixed
    * table:    dataframe with a summary of fixed, missing and not fixed/missing
    """
    return TrackQC(**kwa).trackqualitysummary(tracks, dfmsg)

def beadqualitysummary(trackqc: TrackQC) -> pd.DataFrame:
    """
    a dataframe of frequence of errors per bead per track.  The line bd/trk has
    as many columns as the nb of types of errors that can be detected for a
    bead.  If the bead is missing/fixed all errors are set to NaN
    """
    return trackqc.beadqualitysummary()

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

__all__ = ['TrackQC', 'beadqualitysummary', 'trackqualitysummary', 'mostcommonerror']
