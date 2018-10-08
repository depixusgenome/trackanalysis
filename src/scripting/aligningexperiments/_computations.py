#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scripts for aligning beads & tracks
"""
from   typing                               import Dict, NamedTuple, Optional
from   copy                                 import copy
import pandas                               as     pd
import numpy                                as     np
from   utils                                import initdefaults
from   sequences                            import (Translator,
                                                    read  as _seqread,
                                                    peaks as _seqpeaks)
from   peakcalling.toreference              import Range, CorrectedHistogramFit, Pivot
from   peakcalling.tohairpin                import ChiSquareFit, HairpinFitter
from   model.__scripting__.tasks            import Tasks, Task

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

    kwa.update((i, Tasks(i)(**j)) for i, j in kwa.items() if isinstance(j, dict))
    kwa.update((Tasks(_).name, _) for _ in args)

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

    tgt             = _seqpeaks(seq, target)['position'][0]
    pos['target']   = ((pos.position <= tgt) & (pos.position > (tgt-len(target))))
    pos['expected'] = pos['target'] & pos['strand']
    return HPPositions(seq, target, oligo, pos)

class ZeroFinder:
    """
    Finds the zero position, discarding peaks below
    """
    minratio = .1
    minrate  = .1
    def __call(self, data: pd.DataFrame) -> pd.DataFrame:
        peaks = data.groupby("peakposition").hybridisationrate.first().reset_index()
        peaks.sort_values('peakposition', inplace = True)

        pot   = peaks[peaks.hybridisationrate > self.minrate].peakposition.min()
        rems  = peaks[peaks.peakposition < pot]
        if len(rems) == 0:
            return data

        cnt  = peaks[peaks.peakposition == pot].hybridisationrate.values[0]
        infs = rems[rems.hybridisationrate < cnt*self.minratio]
        out  = infs.peakposition.unique()
        if len(infs) < len(rems):
            out = out[out < np.setdiff1d(rems.peakposition.values, out).min()]
        if len(out):
            return data[data.peakposition.apply(lambda x: x not in out)]
        return data

    def __call__(self, data):
        return (self.__call(data) if isinstance(data, pd.DataFrame) else
                [(i, self.__call(j)) for i, j in data])

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
    peakselector = Tasks.peakselector()
    singlestrand = Tasks.singlestrand()
    findzero     = ZeroFinder()
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

    def maskpeaks(self, data, mask, attribute = 'peakposition'):
        "mask the peaks"
        if callable(self.findzero):
            data = self.findzero(data)

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
        if position is None:
            allp  = lambda x: x.copy()
        else:
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

    def tohairpin(self, data, ref = None, refpos = None, corr = None):
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

        if refpos is None:
            hpalign = self.hpalign
        else:
            hpalign = copy(self.hpalign)
            arr     = [j for i, j in enumerate(hpalign.peaks) if i not in refpos]
            hpalign.peaks = np.array(arr, dtype = 'f4')

        if self.refalign is not None:
            out  = hpalign.optimize(pos[ref])
            corr = {i: (j[0], j[1]*out[1], j[1]*j[2]+out[2]/j[1]) for i, j in corr.items()}
            if self.hprefalign and len(self.hprefalign.peaks):
                pos  = {i: (j-corr[i][2])*corr[i][1] for i, j in pos.items()}
                new  = {i: self.hprefalign.optimize(j)  for i, j in pos.items()}
                corr = {i: (j[0], j[1]*new[i][1], j[1]*j[2]+new[i][2]/j[1])
                        for i, j in corr.items()}
            return corr

        return {i: hpalign.optimize(j) for i, j in pos.items()}

    def correct(self, data, ref, refpos = None):
        """
        translate the data to a common zero
        """
        if ref is None:
            return data
        corr = self.toreference(data, ref)
        corr = self.tohairpin(data, ref, refpos, corr)
        data = [(i, j.assign(peakposition = (j.peakposition-corr[i][2])*corr[i][1],
                             avg          = (j.avg-corr[i][2])*corr[i][1]))
                for i, j in data]

        return data

    def correctionfactors(self, tracks, ref, # pylint: disable=too-many-arguments
                          discarded = None,
                          masks     = None,
                          refpos    = None,
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
        return self.tohairpin(data, ref, refpos, corr)

    def __call__(self, tracks, ref, # pylint: disable=too-many-arguments
                 discarded = None,
                 masks     = None,
                 refpos    = None,
                 pivot     = 'max'):
        if not isinstance(tracks, pd.DataFrame):
            tracks = self.peaks(tracks)

        data = self.split(tracks,
                          discarded = discarded,
                          attribute = 'bead' if isinstance(ref, int) else 'track')
        data = self.maskpeaks(data, masks)
        data = self.setpivot(data, pivot)
        data = self.correct(data, ref, refpos)

        out  = pd.concat([i for _, i in data]).sort_values(['bead', 'modification',
                                                            'peakposition', 'avg'])
        if isinstance(ref, int):
            return out.assign(identity = out.bead.astype(str))
        return out

class PeaksAlignmentConfig(PeaksAlignment):
    """
    config for aligning peaks
    """
    def __init__(self, hpin = None, pivots = None, masks = None, **kwa):
        super().__init__(**kwa)
        self.hpin:   HPPositions = HPPositions(*hpin) if hpin else None
        self.pivots: Dict        = pivots if pivots else {}
        self.masks:  Dict        = masks  if masks else {}
        self.refpos: Dict        = {}
        self.defaultpivot = 'min'
        if self.hpin:
            self.sethppeaks(self.hpin.seq, self.hpin.oligo)

    def alignbead(self, data, key, bead, ref = 'ref'):
        """
        returns the aligned data for the bead
        """
        if np.isscalar(bead):
            return self(data[key][data[key].bead == bead], ref,
                        pivot      = self.pivots.get(bead, self.defaultpivot),
                        masks      = self.masks.get(bead, None),
                        refpos     = self.refpos.get(bead, None))
        return pd.concat([self.alignbead(data, key, i, ref) for i in bead])
