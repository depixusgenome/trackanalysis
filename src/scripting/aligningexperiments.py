#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts for aligning beads & tracks
"""
from   typing                               import Dict, NamedTuple, Any, Optional
import pandas                               as     pd
import numpy                                as     np
import holoviews                            as     hv
from   utils                               import initdefaults
from   sequences                           import (Translator,
                                                   read  as _seqread,
                                                   peaks as _seqpeaks)
from   peakcalling.toreference             import (Range, # pylint: disable=unused-import
                                                   CorrectedHistogramFit, Pivot)
from   peakcalling.tohairpin               import ChiSquareFit, matchpeaks, HairpinFitter
from   peakfinding.groupby.histogramfitter import PeakFlagger
from   model.__scripting__.tasks           import Tasks, Task

def getreference(tracks) -> Optional[str]:
    "returns the reference track"
    return next((i for i in tracks
                 if sum(i.lower().count(j) for j in 'atcg') != len(i)),
                None)

def getoligos(tracks) -> Dict[str, str]:
    "return the oligo for a track"
    return {Translator.reversecomplement(i.lower()): i
            for i in tracks
            if sum(i.lower().count(j) for j in 'atcg') == len(i)}

def createpeaks(tracks, *args: Task, fullstats = True, target = None, **kwa):
    "create peaks for all tracks"
    kwa.update((i, Tasks(i)(**j)) for i, j in kwa.items() if isinstance(j, dict))
    kwa.update((Tasks(_).name, _) for _ in args)

    if target:
        mers  = {Translator.reversecomplement(i): j
                 for i, j in getoligos(tracks).items()}
        lst   = [getreference(tracks)] if getreference(tracks) else []

        size  = max(len(i) for i in mers)
        assert all(len(i) == size for i in mers)
        assert len(mers)+len(lst) == len(tracks)

        targ  = Translator.reversecomplement(target.lower())
        lst  += [mers[targ[k:k+size]]
                 for k in range(len(targ)-size+1) # type: ignore
                 if targ[k:k+size] not in targ[:k+size-1] and targ[k:k+size] in mers]

        tord = pd.DataFrame({'trackorder': np.arange(len(tracks)), 'track': lst})
        tord.set_index('track', inplace = True)

    data = PeaksAlignment(**kwa).peaks(tracks)

    if fullstats:
        vals = [(i, j, k) for i, j in tracks.items()
                for k in data[data.track == i].bead.unique()]
        fdf  = (pd.DataFrame({"hfsigma": [j.rawprecision(k) for i, j, k in vals],
                              "track":   [i for i, j, k in vals],
                              "bead":    [k for i, j, k in vals]})
                .set_index(["track", "bead"]))
        data.set_index(["track", "bead"], inplace = True)
        data = data.join(fdf)

    if target:
        data = data.join(tord)
        data.reset_index(inplace = True)
        data.sort_values('trackorder', inplace = True)
    return data

class HPPositions(NamedTuple): # pylint: disable=missing-docstring
    seq: str
    target: str
    oligo: str
    pos: pd.DataFrame

def hppositions(tracks, fname:str):
    "return a pd.DataFrame of positions"
    allv   = dict(_seqread(fname))
    seq    = allv["full"].upper()
    target = allv["target"].upper()
    oligo  = allv["oligo"].upper()

    ref   = getreference(tracks)
    assert isinstance(ref, str)
    tmp   = {j: _seqpeaks(seq, i)
             for i, j in list(getoligos(tracks).items())+[(ref, ref)]}.items()
    pos   = pd.DataFrame(dict(track    = [i for i, j in tmp for k in j],
                              position = [k for i, j in tmp for k in j['position']],
                              strand   = [k for i, j in tmp for k in j['orientation']]))

    tgt           = _seqpeaks(seq, target)['position'][0]
    pos['target'] = ((pos.position <= tgt) & (pos.position > (tgt-len(target))))
    return HPPositions(seq, target, oligo, pos)

def resolutiongraph(data, *keys: str, rng = (0., 8.)):
    "show resolutions"
    def _fcn(key):
        info = data[key].assign(resolution = data[key].resolution*1e3)
        return hv.BoxWhisker(info, ['trackcount', 'bead'],  'resolution')

    out = (hv.DynamicMap(_fcn, kdims = ['data'])
           .redim.values(data = list(keys))
           .redim.range(resolution = rng))

    return out if len(keys) != 1 else out[keys[0]]

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

    def sethppeaks(self, peaks, oligo = None, hprefalign = False) -> 'PeaksAlignment':
        "sets hairpin peaks"
        if not isinstance(peaks, np.ndarray):
            peaks = HairpinFitter.topeaks(peaks, oligo)

        if self.hpalign:
            self.hpalign.peaks = peaks

        if hprefalign:
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

        if self.refalign is not None:
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
        if ref is None:
            return data
        corr = self.toreference(data, ref)
        corr = self.tohairpin(data, ref, corr)
        data = [(i, j.assign(peakposition = (j.peakposition-corr[i][2])*corr[i][1],
                             avg          = (j.avg-corr[i][2])*corr[i][1]))
                for i, j in data]

        return data

    def correctionfactors(self, tracks, ref, # pylint: disable=too-many-arguments
                          discarded = None,
                          masks     = None,
                          pivot     = 'max'):
        "return the correction factors for the different beads or tracks"
        if not isinstance(tracks, pd.DataFrame):
            tracks = self.peaks(tracks)

        data = self.split(tracks,
                          discarded = discarded,
                          attribute = 'bead' if isinstance(ref, int) else 'track')
        data = self.maskpeaks(data, masks)
        data = self.setpivot(data, pivot)
        corr = self.toreference(data, ref)
        return self.tohairpin(data, ref, corr)

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
                  style = dict(alpha  = .2))
                ).redim.label(avg = 'base pairs')
                *(hv.Scatter(data, ref, cols, label = 'peaks')
                  (plot  = dict(size_index     = 'resolution',
                                scaling_factor = 15000),
                   style = dict(alpha = .01, line_alpha=.1))
                 ).redim.label(**{cols[0]: 'base pairs'})
               )

        args = dict(style = dict(color = 'gray', alpha = .5, size = 5), group = 'ref')
        for i, j in seqs.items():
            out = self.hpindisplay(data, j, ref, label = i, **args)*out

        return out if self.hpalign else out

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

class PeaksAlignmentConfig(PeaksAlignment):
    """
    config for aligning peaks
    """
    def __init__(self, hpin = None, pivots = None, masks = None, **kwa):
        super().__init__(**kwa)
        self.hpin:   HPPositions    = HPPositions(*hpin) if hpin else None
        self.pivots: Dict[int, Any] = pivots if pivots else {}
        self.masks:  Dict[int, Any] = masks  if masks else {}
        if self.hpin:
            self.sethppeaks(self.hpin.seq, self.hpin.oligo)

    def show(self, data, # pylint: disable=too-many-arguments
             keys       = (),
             beads      = (),
             trackorder = 'trackorder',
             align      = True) -> hv.DynamicMap:
        "return a dynamic map"
        def _fcn(key, bead):
            return self.display(data[key][data[key].bead == bead], 'ref',
                                trackorder = trackorder,
                                align      = align,
                                pivot      = self.pivots.get(bead, 'min'),
                                masks      = self.masks.get(bead, None))

        out = (hv.DynamicMap(_fcn, kdims = ['data', 'bead'])
               .redim.values(data = list(keys), bead = list(beads)))
        if self.hpin:
            pos    = self.hpin.pos
            tracks = list(pos.track.unique())
            ref    = pos[pos.track == getreference(tracks)].position.values
            out    = (out
                      *hv.Scatter(pos[pos.target & pos.strand], 'track', 'position')
                      (style ={'color':'green'})
                      *hv.Scatter(pos[pos.target & ~pos.strand], 'track', 'position')
                      (style ={'color':'red'})
                      *hv.Scatter((np.repeat(tracks, ref.size),
                                   np.concatenate([ref]*len(tracks))))
                      (style ={'color':'gray'})
                     )
        return out
