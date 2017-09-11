#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for oligo mapping purposes"
import sys
from   typing           import List, Type
import numpy            as np
from   utils.decoration import addto
import sequences
from   ..processor      import PeaksDict, BeadsByHairpinProcessor
from   ..toreference    import ReferenceDistance

def _get(name, val = None):
    mod = sys.modules[name]
    return mod if val is None else getattr(mod, val)

hv               = _get('holoviews')                             # pylint: disable=invalid-name
_peakfinding     = _get('peakfinding.__scripting__.holoviewing') # pylint: disable=invalid-name
Tasks:      Type = _get('model.__scripting__', 'Tasks')
TracksDict: Type = _get('data.__scripting__', 'TracksDict')

class OligoMappingDisplay(_peakfinding.PeaksDisplay): # type: ignore
    "displays peaks & oligos"
    @staticmethod
    def hpins(seq, oligos, labels, **opts):
        "returns haipin positions"
        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])
        style = opts.pop('sequencestyle', dict(color = 'gray'))
        pks = {}
        if labels is not False:
            opts['label'] = 'sequence'
        for key, vals in sequences.peaks(seq, oligos):
            xvals = np.repeat(vals['position'], 3)
            yvals = np.concatenate([[(0, 1)[plus], (1, 2)[plus], np.NaN]
                                    for plus in vals['orientation']])
            pks[key] = hv.Curve((xvals, yvals), **opts)(style = style)
        return pks

    @classmethod
    def fitmap(cls, itms, seq, oligos, labels = None, **opts):
        "creates a DynamicMap with fitted oligos"
        pins = cls.hpins(seq, oligos, opts)
        task = Tasks.beadsbyhairpin.get(sequence = seq, oligos = oligos)
        info = {i: [(k.key, k.distance) for k in j.beads]
                for i, j in BeadsByHairpinProcessor.apply(itms, **task.config())}

        def _fcn(bead):
            for key, other in info.items():
                dist = next((j for i, j in other if i == bead), None)
                if dist is None:
                    continue

                crv = cls.elements(itms[[bead]], labels, **opts,
                                   stretch = dist.stretch,
                                   bias    = dist.bias,
                                   group   = key)
                return hv.Overlay(crv+[pins[key]], group = key)

        beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)

    @classmethod
    def hpinmap(cls, itms, seq, oligos, labels = None, **opts):
        "creates a DynamicMap with oligos to fit"
        pins = cls.hpins(seq, oligos, opts)
        def _clone(itm, stretch, bias):
            data = np.copy(itm.data)
            data[:,0] = (data[:,0]-bias)*stretch
            return itm.clone(data = data)

        # pylint: disable=dangerous-default-value
        def _over(bead, sequence, stretch, bias, cache = [None, ()]):
            if bead != cache[0]:
                cache[0] = bead
                cache[1] = cls.elements(itms[[bead]], labels, **opts)
            clones = [_clone(i, stretch, bias) for i in cache[1]]
            return hv.Overlay(clones+[pins[sequence]])

        beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
        rngs  = Tasks.getconfig().fittohairpin.getitems(...)
        return (hv.DynamicMap(_over, kdims = ['sequence', 'bead', 'stretch', 'bias'])
                .redim.values(bead    = beads, sequence = list(pins.keys()))
                .redim.range(**rngs))

@addto(PeaksDict)  # type: ignore
def display(self, # pylint: disable=function-redefined,too-many-arguments
            kdim     = 'bead',
            labels   = None,
            sequence = None,
            oligos   = None,
            fit      = False, **opts):
    """
    Displays peaks.

    Arguments are:

        * *kdim*: if 'bead', then a *holoviews.DynamicMap* is returned, displaying
        beads independently.
        * *precision* is the noise level used to find peaks
        * *labels*: if *False*, no labels are added. If *None*, labels are added
        if 3 or less beads are shown.
        * *sequence* and *oligo*: can be used to display dna positions. If
        *fit* is *False*, then the returned dynamic map will have *sequence*,
        *stretch* and *bias* widgets as well as *bead*.
        * *stretch* and *bias* values can be provided manually
        * *zero* set to *True* will set the x-axis zero to the first peak position.
        * *fit*: if used in conjunction with *sequence* and *oligo*, each bead
        will be displayed with the best fit sequence.
        * *sequencestyle*, *eventstyle*, *peakstyle* can be used to set the style
        of corresponding graph elements.
    """
    disp = OligoMappingDisplay
    if None not in (sequence, oligos):
        if fit:
            return disp.fitmap(self, sequence, oligos, labels, **opts)
        return disp.hpinmap(self, sequence, oligos, labels, **opts)

    if None not in (sequence, oligos):
        return disp.hpinmap(self, sequence, oligos, labels)

    if kdim == 'bead':
        beads = list(set([i for i in self.keys() if self.isbead(i)]))
        def _fcn(bead):
            return disp.run(self[[bead]], labels, **opts)
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
    return disp.run(self, labels, **opts)

class PeaksTracksDictDisplay(_peakfinding.PeaksTracksDictDisplay): # type: ignore
    "tracksdict display for peaks"
    @classmethod
    def _all(cls, specs, fcn, key):
        ovrs = super()._all(specs, fcn, key)
        if None in (specs['reference'], specs['distance']):
            return ovrs

        dist = specs['distance']
        ind  = cls._refindex(specs)
        ref  = next(iter(ovrs[ind])).data
        for i, j in enumerate(ovrs):
            if i == ind:
                continue
            stretch, bias = dist.optimize(ref, next(iter(j)).data)[1:]
            for itm in j:
                itm.data[:,0]   = (itm.data[:,0] - bias)*stretch
        return cls._toarea(specs, ovrs)

    @classmethod
    def _specs(cls):
        return super()._specs() + (('distance', ReferenceDistance()),)

@addto(TracksDict) # type: ignore
def peaks(self, overlay = 'key', reference = None, **kwa):
    """
    A hv.DynamicMap showing peaks

    Options are:

        * *overlay* == 'key': for a given bead, all tracks are overlayed:

            * *reference*: the reference is displayed as an area
            * *distance*: a *ReferenceDistance* object (default) or *None*. This
            objects computes a stretch and bias which is applied to the x-axis of
            non-reference items.

        * *overlay* == 'bead': for a given track, all beads are overlayed

            * *reference*: the reference is displayed as an area
            * *distance*: a *ReferenceDistance* object (default) or *None*. This
            objects computes a stretch and bias which is applied to the x-axis of
            non-reference items.

        * *overlay* == None:

            * *reference*: the reference is removed from the *key* widget and
            allways displayed to the left independently.
            * *refdims*: if set to *True*, the reference gets its own dimensions.
            Thus zooming and spanning is independant.
            * *reflayout*: can be set to 'top', 'bottom', 'left' or 'right'

    """
    kwa.setdefault('reflayout', 'bottom')
    return PeaksTracksDictDisplay.run(self, 'peaks', overlay, reference, kwa)

__all__: List[str] = []
