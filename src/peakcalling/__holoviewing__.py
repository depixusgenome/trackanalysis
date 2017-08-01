#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Updating PeaksDict for scripting purposes"
import sys
from   typing           import List
from   functools        import partial
import numpy            as np
import holoviews        as hv
from   utils.decoration import addto
import sequences
from   .processor       import PeaksDict, BeadsByHairpinProcessor

Display: type = sys.modules['data.__holoviewing__'].Display
Tasks:   type = sys.modules['model.__scripting__'].Tasks

class PeaksDisplay(Display): # type: ignore
    "displays the events"
    # pylint: disable=too-many-arguments,arguments-differ
    @classmethod
    def elements(cls, evts, labels, **opts):
        "shows overlayed Curve items"
        prec   = opts.pop('precision', None)
        pstyle = opts.pop('peakstyle',  dict(size = 5, color = 'green'))
        estyle = opts.pop('eventstyle', dict(size = 3))
        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])
        stretch = opts.pop('stretch', 1.)
        bias    = opts.pop('bias', 0.)

        itms    = []
        for bead in evts.keys():
            det   = evts.detailed(bead, prec)
            xvals = np.arange(len(det.histogram))*det.binwidth+det.minvalue
            xvals = (xvals-bias)*stretch
            if labels is not False:
                opts['label'] = 'histogram'
            itms.append(hv.Curve((xvals, det.histogram), **opts)(style = estyle))

            xvals = (np.concatenate(det.positions)-bias)*stretch
            yvals = [itms[-1][i] for i in xvals]
            itms.append(hv.Scatter((xvals, yvals), **opts)(style = estyle))

            xvals = [(i-bias)*stretch for i, _ in evts.config.details2output(det)]
            yvals = [itms[-2][i] for i in xvals]
            if labels is not False:
                opts['label'] = 'peaks'
            itms.append(hv.Scatter((xvals, yvals), **opts)(style = pstyle))
        return itms

    @classmethod
    def run(cls, evts, labels, **opts):
        "shows overlayed Curve items"
        return hv.Overlay(cls.elements(evts, labels, **opts))

    @classmethod
    def hpins(cls, seq, oligos, labels, **opts):
        "returns haipin positions"
        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])
        style = opts.pop('sequencestyle', dict(color = 'gray'))
        peaks = {}
        if labels is not False:
            opts['label'] = 'sequence'
        for key, vals in sequences.peaks(seq, oligos):
            xvals = np.repeat(vals['position'], 3)
            yvals = np.concatenate([[(0, 1)[plus], (1, 2)[plus], np.NaN]
                                    for plus in vals['orientation']])
            peaks[key] = hv.Curve((xvals, yvals), **opts)(style = style)
        return peaks

    @classmethod
    def fitmap(cls, itms, seq, oligos, labels = None, **opts):
        "creates a DynamicMap with fitted oligos"
        hpins = cls.hpins(seq, oligos, opts)
        task  = Tasks.beadsbyhairpin.get(sequence = seq, oligos = oligos)
        info  = {i: [(k.key, k.distance) for k in j.beads]
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
                return hv.Overlay(crv+[hpins[key]], group = key)

        beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)

    @classmethod
    def hpinmap(cls, itms, seq, oligos, labels = None, **opts):
        "creates a DynamicMap with oligos to fit"
        hpins = cls.hpins(seq, oligos, opts)
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
            return hv.Overlay(clones+[hpins[sequence]])

        beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
        rngs  = Tasks.getconfig().fittohairpin.getitems(...)
        return (hv.DynamicMap(_over, kdims = ['sequence', 'bead', 'stretch', 'bias'])
                .redim.values(bead    = beads, sequence = list(hpins.keys()))
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
        * *labels*: if *False*, no labels are added. If *None*, labels are added
        if 3 or less beads are shown.
        * *sequence* and *oligo*: can be used to display dna positions. If
        *fit* is *False*, then the returned dynamic map will have *sequence*,
        *stretch* and *bias* widgets as well as *bead*.
        * *fit*: if used in conjunction with *sequence* and *oligo*, each bead
        will be displayed with the best fit sequence.

    Other options are:

        * *sequencestyle*, *eventstyle*, *peakstyle* can be used to set the style
        of corresponding graph elements.
        * *stretch* and *bias* can be used to set the *z* axis range.
    """
    disp = PeaksDisplay
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

@addto(PeaksDict)
def map(self, fcn, **kwa): # pylint: disable=redefined-builtin
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

__all__: List[str] = []
