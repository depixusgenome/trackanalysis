#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts for aligning beads & tracks
"""
from   concurrent.futures      import ProcessPoolExecutor, as_completed
from   typing                  import Tuple, List

import pandas                  as     pd
import numpy                   as     np
import holoviews               as     hv

from   utils                   import initdefaults
from   utils.logconfig         import getLogger
from   peakfinding.processor   import SingleStrandProcessor, SingleStrandTask
from   peakcalling.toreference import (CorrectedHistogramFit, # pylint: disable=unused-import
                                       Range, Pivot)
from   peakcalling.tohairpin   import ChiSquareFit

LOGS = getLogger()

class PeaksDataFrameCreator:
    "Create the datafame"
    dataframe    = dict(events = dict(std = 'std'), resolution = 'resolution')
    singlestrand = SingleStrandTask()

    @initdefaults(frozenset(locals()))
    def __init__(self, **_):
        pass

    def _create(self, trk) -> Tuple[pd.DataFrame, List[int]]:
        trk.tasks.selection = None
        pks    = SingleStrandProcessor.apply(trk.peaks, **self.singlestrand.config())
        create = lambda i: (pks[[i]].dataframe(**self.dataframe)).reset_index()
        good   = []
        bad    = []
        for i in trk.cleaning.good():
            try:
                good.append(create(i))
            except: # pylint: disable=bare-except
                bad.append(i)
        return pd.concat(good), bad

    @staticmethod
    def _dataframe(tracks, full):
        data = (pd.concat(full)
                .reset_index()
                .set_index('track')
                .join(tracks
                      .dataframe()[['key', 'modification']]
                      .rename(columns = dict(key = 'track'))
                      .set_index('track'))
                .reset_index('track')
                .sort_values(['modification'])
               )

        data = data.assign(bead = data.bead.astype(int))
        if 'index' in data.columns:
            del data['index']

        return data

    def __call__(self, tracks) -> pd.DataFrame:
        full = []
        with ProcessPoolExecutor() as pool:
            futs = [pool.submit(self._create, i) for i in tracks.values()]
            for fut in as_completed(futs):
                try:
                    data, err = fut.result()
                    full.append(data)
                    if len(err):
                        track = data.reset_index().track.unique()
                        if len(track):
                            LOGS.info("error in %s: %s", track[0], err)
                        else:
                            LOGS.info("error beads: %s", err)
                except Exception as exc: # pylint: disable=broad-except
                    LOGS.info("error: %s", exc)

        return self._dataframe(tracks, full)

    @classmethod
    def create(cls, tracks):
        "create peaks for all tracks"
        import scripting
        return cls(singlestrand = getattr(scripting, 'Tasks').singlestrand())(tracks)

createpeaks = PeaksDataFrameCreator.create # pylint: disable=invalid-name

class PeaksAlignment:
    """
    Align beads or tracks
    """
    def __init__(self, **kwa):
        self.hpalign  = kwa['hpalign']  if 'hpalign'  in kwa else ChiSquareFit(**kwa)
        self.refalign = kwa['refalign'] if 'refalign' in kwa else CorrectedHistogramFit(**kwa)
        if self.refalign and 'pivot' not in kwa:
            self.refalign.pivot = Pivot.absolute
        if self.hpalign and 'firstpeak' not in kwa:
            self.hpalign.firstpeak = False

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

    def tohairpin(self, data, ref, corr):
        """
        normalize to a given hairpin
        """
        if not self.hpalign:
            return corr
        pks = np.sort(next(j for i, j in data if i == ref).peakposition.unique())
        out = self.hpalign.optimize(pks)
        return {i: (j[0], j[1]*out[1], j[1]*j[2]+out[2]/j[1]) for i, j in corr.items()}

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

    def __call__(self, tracks, ref,
                 discarded = None,
                 masks     = None):
        data = self.split(tracks,
                          discarded = discarded,
                          attribute = 'bead' if isinstance(ref, int) else 'track')
        data = self.maskpeaks(data, masks)
        data = self.setpivot(data)
        data = self.correct(data, ref)

        out  = pd.concat([i for _, i in data]).sort_values(['bead', 'track', 'peakposition', 'avg'])
        if isinstance(ref, int):
            return out.assign(identity = out.bead.astype(str))
        return out

    def display(self,   # pylint: disable=too-many-arguments
                data,
                ref       = None,
                discarded = None,
                masks     = None,
                align     = True,
                **seqs):
        "display the data"
        if align:
            data = self(data, ref, discarded=discarded, masks=masks)
            ref  = None

        data = data.sort_values(['bead', 'track', 'peakposition', 'avg'])
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
