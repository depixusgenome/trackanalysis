#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts for aligning beads & tracks
"""
from   typing                               import Dict
import pandas                               as     pd
import numpy                                as     np
import holoviews                            as     hv # pylint: disable=import-error

from   utils                               import initdefaults
from   peakcalling.toreference             import (Range, # pylint: disable=unused-import
                                                   CorrectedHistogramFit, Pivot)
from   peakcalling.tohairpin               import ChiSquareFit, matchpeaks
from   peakfinding.groupby.histogramfitter import PeakFlagger
from   model.__scripting__.tasks           import Tasks

def createpeaks(tracks):
    "create peaks for all tracks"
    return PeaksAlignment().peaks(tracks)

class PeaksAlignment:
    """
    Align beads or tracks
    """
    refalign     = CorrectedHistogramFit(pivot     = Pivot.absolute,
                                         firstpeak = False,
                                         stretch   = Range(1., .15, .03),
                                         bias      = Range(0., .008, .002))
    hpalign      = ChiSquareFit         (pivot     = Pivot.top,
                                         firstpeak = False,
                                         bias      = Range(None, .01,  .005))
    hprefalign   = ChiSquareFit         (pivot     = Pivot.top,
                                         firstpeak = False,
                                         stretch   = Range(1.,   .05, .01),
                                         bias      = Range(None, .01, .005))
    peakflagger  = PeakFlagger          (mincount = 1, window = 15)
    peakselector = Tasks.peakselector()
    singlestrand = Tasks.singlestrand()
    individually = False

    @initdefaults(frozenset(locals()),
                  hppeaks = lambda self, val: self.sethppeaks(val))
    def __init__(self, **kwa):
        pass

    def sethppeaks(self, peaks) -> 'PeaksAlignment':
        "sets hairpin peaks"
        if self.hpalign:
            self.hpalign.peaks = peaks

        if self.hprefalign.peaks:
            self.hprefalign.peaks = peaks
        return self

    def peaks(self, tracks) -> pd.DataFrame:
        """
        creates a peaks dataframe
        """
        return (tracks
                .dataframe(self.peakselector, self.singlestrand,
                           events     = dict(std = 'std'),
                           resolution = 'resolution')
                .reset_index())

    @staticmethod
    def split(data, discarded = None, attribute = 'bead'):
        "split the data by beads or tracks"
        data  = data.reset_index().sort_values(['track', 'bead', 'peakposition'])
        items = [(i, data[data[attribute] == i]) for i in data[attribute].unique()]
        if discarded:
            return [(i, j) for i, j in items if i not in discarded]
        return items

    @classmethod
    def maskpeaks(cls, data, mask, attribute = 'peakposition'):
        "mask the peaks"
        if mask is None:
            return data

        def _maskpeaks(itm, msk):
            if msk is None:
                return itm

            vals = np.sort(itm[attribute].unique())
            if isinstance(msk, int):
                return itm[itm[attribute] < vals[msk]]

            vals = frozenset(vals[msk])
            return itm[itm[attribute].transform(lambda x: x not in vals)]

        if isinstance(mask, dict):
            if isinstance(data, dict):
                data = data.items()
            return [(i, _maskpeaks(j, mask.get(i, None))) for i, j in data]
        return _maskpeaks(data, mask)

    def flagpeaks(self, ref, data, attr = 'peakposition'):
        """
        Return pairs of peaks per bead and track.
        The peak & event positions should already be aligned
        """
        inf                   = np.iinfo('i4').max
        cols: Dict[str, list] = {i: [] for i in ('track', 'bead', attr, 'reference')}
        for bead, track in {k[1:] for k in data[['bead', 'track']].itertuples()}:
            thisref  = ref[track] if isinstance(ref, dict) else ref
            tmp      = data[data.bead==bead]
            peaks    = np.sort(tmp[tmp.track == track][attr].unique())
            if attr == 'peakposition':
                flags = matchpeaks(thisref, peaks, self.peakflagger.window)
            else:
                flags = self.peakflagger(thisref, [peaks])[0]

            cols['reference'].append(thisref[flags[flags < inf]])
            cols[attr].append(peaks[flags < inf])
            cols['track'].append([track]*len(cols[attr][-1]))
            cols['bead'].append(np.full(len(cols[attr][-1]), bead, dtype = 'i4'))

        out = pd.DataFrame({i: np.concatenate(j) for i, j in cols.items()})
        out = out.assign(delta = out.peakposition-out.reference)
        return out.join(out
                        .groupby('bead')
                        .agg(dict(reference = 'count', delta = lambda x: np.abs(x).mean()))
                        .rename(columns = dict(reference = 'peakcount', delta = 'residual')),
                        on = ['bead'])

    @staticmethod
    def setpivot(data, position = 'max'):
        "moves peakposition and avg to a new position"
        pos   = lambda attr, x: x[attr] - getattr(x.peakposition, position)()
        allp  = lambda x: x.assign(peakposition = pos('peakposition', x),
                                   avg          = pos('avg', x))
        if isinstance(data, pd.DataFrame):
            return allp(data)
        return [(i, allp(j)) for i, j in data]

    def toreference(self, data, ref):
        """
        normalize to a given bead or track
        """
        if not self.refalign:
            return {i: (0., 1., 0.) for i, _ in data}
        frompks = lambda pks: (pks
                               .groupby('peakposition')
                               .resolution
                               .first()
                               .reset_index()
                               .values)
        pks     = {i: self.refalign.frompeaks(frompks(j)) for i, j in data}
        return {i: self.refalign.optimize(pks[ref], j) for i, j in pks.items()}

    def tohairpin(self, data, ref = None, corr = None):
        """
        normalize to a given hairpin
        """
        if not self.hpalign:
            return corr

        pos = {i: np.sort(j.peakposition.unique()) for i, j in data}
        if self.individually:
            pos = {i: (j-corr[i][2])*corr[i][1] for i, j in pos.items()}
            new = {i: self.hpalign.optimize(j)  for i, j in pos.items()}
            return {i: (j[0], j[1]*new[i][1], j[1]*j[2]+new[i][2]/j[1]) for i, j in corr.items()}

        elif self.refalign is not None:
            out  = self.hpalign.optimize(pos[ref])
            corr = {i: (j[0], j[1]*out[1], j[1]*j[2]+out[2]/j[1]) for i, j in corr.items()}
            if self.hprefalign and len(self.hprefalign.peaks):
                pos  = {i: (j-corr[i][2])*corr[i][1] for i, j in pos.items()}
                new  = {i: self.hprefalign.optimize(j)  for i, j in pos.items()}
                corr = {i: (j[0], j[1]*new[i][1], j[1]*j[2]+new[i][2]/j[1])
                        for i, j in corr.items()}
            return corr

        return {i: self.hpalign.optimize(j) for i, j in pos.items()}

    def correct(self, data, ref):
        """
        translate the data to a common zero
        """
        corr = self.toreference(data, ref)
        corr = self.tohairpin(data, ref, corr)
        data = [(i, j.assign(peakposition = (j.peakposition-corr[i][2])*corr[i][1],
                             avg          = (j.avg-corr[i][2])*corr[i][1]))
                for i, j in data]

        return data

    def __call__(self, tracks, ref, # pylint: disable=too-many-arguments
                 discarded = None,
                 masks     = None,
                 pivot     = 'max'):
        if not isinstance(tracks, pd.DataFrame):
            tracks = self.peaks(tracks)

        data = self.split(tracks,
                          discarded = discarded,
                          attribute = 'bead' if isinstance(ref, int) else 'track')
        data = self.maskpeaks(data, masks)
        data = self.setpivot(data, pivot)
        data = self.correct(data, ref)

        out  = pd.concat([i for _, i in data]).sort_values(['bead', 'modification',
                                                            'peakposition', 'avg'])
        if isinstance(ref, int):
            return out.assign(identity = out.bead.astype(str))
        return out

    def display(self,   # pylint: disable=too-many-arguments
                data,
                ref        = None,
                discarded  = None,
                masks      = None,
                align      = True,
                pivot      = 'max',
                trackorder = 'modification',
                **seqs):
        "display the data"
        if not isinstance(data, pd.DataFrame):
            data = self.peaks(data)

        if align:
            data = self(data, ref, discarded=discarded, masks=masks, pivot=pivot)
            ref  = None

        data = data.sort_values(['bead', trackorder, 'peakposition', 'avg'])
        if ref is None:
            ref  = 'identity' if 'identity' in data.columns else 'track'
        cols = ['peakposition', 'resolution']
        out  = ((hv.Scatter(data, ref, 'avg', label = 'events')
                 (plot  = dict(jitter = .75),
                  style = dict(alpha  = .2)))
                *(hv.Scatter(data, ref, cols, label = 'peaks')
                  (plot  = dict(size_index     = 'resolution',
                                scaling_factor = 10000 ),
                   style = dict(alpha = .01)))
               )

        args = dict(style = dict(color = 'gray', alpha = .5, size = 5), group = 'ref')
        for i, j in seqs.items():
            out = self.hpindisplay(data, j, ref, label = i, **args)*out

        return out.redim(avg = 'base pairs') if self.hpalign else out

    @staticmethod
    def hpindisplay(data, positions,
                    ref   = None,
                    plot  = None,
                    style = None,
                    **args):
        """
        display hairpin positions
        """
        if ref is None:
            ref  = 'identity' if 'identity' in data.columns else 'track'
        xvals = list(set(data[ref].unique()))
        out   = hv.Scatter((xvals * len(positions),
                            np.repeat(positions, len(xvals))), **args)
        return out(plot  = plot  if plot else dict(),
                   style = style if style else dict())
