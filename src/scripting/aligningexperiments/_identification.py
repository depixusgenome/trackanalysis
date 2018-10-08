#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts for aligning beads & tracks
"""
from   typing                               import Dict
import pandas       as     pd
import numpy        as     np

from   peakfinding.groupby.histogramfitter  import PeakFlagger
from   peakcalling.tohairpin                import matchpeaks
from   utils                                import EventsArray

class PeakIdentifier:
    """
    Tools for flagging the reference peaks
    """
    peakflagger  = PeakFlagger(mincount = 1, window = 10)
    def __call__(self, ref, data, attr = 'peakposition'):
        """
        Return pairs of peaks per bead and track.
        The peak & event positions should already be aligned
        """
        inf                   = np.iinfo('i4').max
        cols: Dict[str, list] = {i: [] for i in ('track', 'bead', attr, 'reference')}
        for bead, track in {k[1:] for k in data[['bead', 'track']].itertuples()}:
            thisref  = np.asarray(ref        if isinstance(ref, np.ndarray) else
                                  ref[track] if isinstance(ref, dict)       else
                                  ref[ref.track == track].position,
                                  dtype = 'f4')
            tmp      = data[data.bead==bead]
            peaks    = np.sort(tmp[tmp.track == track][attr].unique())
            if attr == 'peakposition':
                flags = matchpeaks(thisref, peaks.astype("f4"), 10.)
            else:
                flags = self.peakflagger(thisref, [peaks])[0]
            cols['reference'].append(thisref[flags[flags < inf]].astype('i4'))
            cols[attr].append(peaks[flags < inf])
            cols['track'].append([track]*len(cols[attr][-1]))
            cols['bead'].append(np.full(len(cols[attr][-1]), bead, dtype = 'i4'))

        out = pd.DataFrame({i: np.concatenate(j) for i, j in cols.items()})
        out['reference'] = out['reference'].astype('i4')
        out['delta']     = out.peakposition-out.reference
        out.set_index(["track", "bead", "peakposition"], inplace = True)
        return data.set_index(["track", "bead", "peakposition"]).join(out)

    @staticmethod
    def expectedpeaksdata(data, pos):
        "keeps only hairpin data"
        hpins = (data.dropna()
                 [['averageduration', 'eventcount', 'hybridisationrate', 'resolution',
                   'modification', 'trackcount', 'trackorder', 'delta', 'hfsigma',
                   'reference']]
                 .groupby(level=[0,1,2])
                 .first()
                 .reset_index(level = 2)
                 .set_index('reference', append = True))

        seqpos      = pos[pos.expected].set_index("track").position
        inds: list  = []
        for i, j in hpins.groupby(level = [0, 1]).hfsigma.first().index:
            pos  = seqpos.loc[i]
            if np.isscalar(pos):
                inds.append((i, j, pos))
            else:
                inds.extend((i, j, k) for k in pos)
        return hpins.reindex(inds)

class FalsePositivesIdentifier:
    "flag false positives"
    @classmethod
    def falsepositives(cls, data):
        "dataframe"
        fpos = (data[lambda x: x.reference.isna()]
                .reset_index()
                .sort_values('peakposition')
                .assign(bead = lambda x: x.bead.astype('str')))
        fpos.rename(columns = dict(avg = "z"), inplace = True)
        return fpos

    @classmethod
    def detailed(cls, config, data, precision = 1):
        "return detailed info about the peak selection"
        evts = (data.groupby(["bead", "peakposition"])
                .z.unique()
                .groupby(level=[0, 1])
                .apply(cls._toevts).values)
        return config.detailed(evts, precision = precision)

    @staticmethod
    def _toevts(vals):
        vals = vals.values
        start = np.cumsum(np.array([0]+[len(i) for i in vals]))
        return EventsArray(list(zip(start, vals)))
