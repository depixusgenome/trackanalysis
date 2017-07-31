#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import inspect
from   functools                import partial
from   itertools                import chain, repeat
import numpy                    as np
import holoviews                as hv
import holoviews.operation      as hvops
import sequences
from   data.trackitems          import Beads, Cycles
from   eventdetection.data      import Events
from   peakfinding.processor    import PeaksDict
from   peakcalling.processor    import BeadsByHairpinProcessor
from   .track                   import ExperimentList, Track
from   .scriptapp               import Tasks

if 'ipykernel_launcher' in inspect.stack()[-3].filename:
    try:
        import bokeh.io as _io
        _io.output_notebook()
        hv.notebook_extension('bokeh')
        from IPython import get_ipython
        get_ipython().magic('output size=150')
    except:                                         # pylint: disable=bare-except
        pass

def _add(*types):
    def _wrapper(fcn):
        for tpe in types:
            setattr(tpe, getattr(fcn, 'fget', fcn).__name__, fcn)
    return _wrapper

class Display:
    "displays the beads or cycles"
    @staticmethod
    def concat(itr):
        "concatenates arrays, appending a NaN"
        return np.concatenate(list(chain.from_iterable(zip(itr, repeat([np.NaN])))))

    @staticmethod
    def _create(labels, tpe, overlay, opts, good):
        opts.setdefault('kdims', ['frames'])
        opts.setdefault('vdims', ['z'])
        if isinstance(tpe, str):
            tpe = getattr(hv, tpe) if hasattr(hv, tpe) else getattr(hv, tpe.capitalize())
        if len(good) < 3 or labels is True:
            crvs = [tpe(j, label = f'{i}', **opts) for i, j in good]
        else:
            crvs = [tpe(j, **opts) for _, j in good]
        return crvs[0] if len(crvs) == 1 and overlay is False else hv.Overlay(crvs)

    @classmethod
    def run(cls, itms, labels, tpe, overlay, opts): # pylint: disable=too-many-arguments
        "shows overlayed Curve items"
        good = ((i, j) for i, j in itms if np.any(np.isfinite(j)))
        if overlay:
            good = tuple(good)
        else:
            good = (('', cls.concat(i for _, i in good)),)
        return cls._create(labels, tpe, overlay, opts, good)

class EventDisplay(Display):
    "displays the events"
    @classmethod
    def run(cls, itms, labels, tpe, overlay, opts): # pylint: disable=too-many-arguments
        "shows overlayed Curve items"
        vals = lambda x: (cls.concat([np.arange(i[0], i[0]+len(i[1])) for i in x]),
                          cls.concat(x['data']))
        good = tuple((i, vals(j)) for i, j in itms if len(j))
        if not overlay:
            good = (('', (cls.concat(i[0] for _, i in good),
                          cls.concat(i[1] for _, i in good))),)
        return cls._create(labels, tpe, overlay, opts, good)

class PeaksDisplay(Display):
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

@_add(Beads)
def display(self,
            kdim    = 'bead',
            labels  = None,
            tpe     = 'curve',
            overlay = True,
            **opts):
    """
    Displays beads.

    Arguments are:

        * *kdim*: if 'bead', then a *holoviews.DynamicMap* is returned, displaying
        beads independently.
        * *labels*: if *False*, no labels are added. If *None*, labels are added
        if 3 or less beads are shown.
        * *tpe*: can be scatter or curve.
        * *overlay*: if *False*, all data is concatenated into one array.
    """
    disp = Display.run
    if kdim == 'bead':
        beads = list(set([i for i in self.keys() if self.isbead(i)]))
        def _fcn(bead):
            return disp(self[[bead]], labels, tpe, overlay, opts)
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
    return disp(self, labels, tpe, overlay, opts)

@_add(PeaksDict)  # type: ignore
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
            return disp.run(self[[bead]], labels, opts)
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
    return disp.run(self, labels, opts)

@_add(Events, Cycles)   # type: ignore
def display(self,       # pylint: disable=function-redefined
            kdim    = 'bead',
            labels  = None,
            tpe     = 'curve',
            overlay = True,
            **opts):
    """
    Displays cycles.

    Arguments are:

        * *kdim*: if set to 'bead', then a *holoviews.DynamicMap* is returned,
        displaying beads independently. If set to 'cycle', the map displays cycles
        independently.
        * *labels*: if *False*, no labels are added. If *None*, labels are added
        if 3 or less beads are shown.
        * *tpe*: can be scatter or curve.
        * *overlay*: if *False*, all data is concatenated into one array.
    """
    disp = (EventDisplay if isinstance(self, Events) else Display).run
    if kdim == 'cycle':
        itms = list(set([i for _, i in self.keys() if Beads.isbead(i)]))
        def _percycle(cyc):
            return disp(self[...,cyc], labels, tpe, overlay, opts)
        fcn  = _percycle
    elif kdim == 'bead':
        itms = list(set([i for i, _ in self.keys() if Beads.isbead(i)]))
        def _perbead(bead):
            return disp(self[bead,...], labels, tpe, overlay, opts)
        fcn  = _perbead
    else:
        return disp(self, labels, tpe, overlay, opts)

    return hv.DynamicMap(fcn, kdims = [kdim]).redim.values(**{kdim: itms})

@_add(Beads, Track, Beads, PeaksDict)
def map(self, fcn, **kwa): # pylint: disable=redefined-builtin
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@_add(Cycles, Events)  # type: ignore
def map(self, fcn, kdim = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap with beads or cycles, as well as kwargs in the kdims"
    if kdim is None:
        kdim = 'cycle' if ('cycle' in kwa and 'bead' not in kwa) else 'bead'

    if kdim == 'bead':
        kwa.setdefault(kdim, list(set(i for _, i in self.keys())))
    elif kdim == 'cycle':
        kwa.setdefault(kdim, list(set(i for i, _ in self.keys())))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@_add(ExperimentList)
def oligomap(self:ExperimentList, oligo, fcn, **kwa):
    "returns a hv.DynamicMap with oligos and beads in the kdims"
    oligos = self.allkeys(oligo)
    beads  = self.available(*oligos)
    print(oligos, beads)
    return (hv.DynamicMap(fcn, kdims = ['oligo', 'bead'] + list(kwa))
            .redim.values(oligo = oligos, bead = beads, **kwa))

@_add(ExperimentList)
def keymap(self:ExperimentList, key, fcn, **kwa):
    "returns a hv.DynamicMap with keys in the kdims"
    beads  = self.available(*self.convert(key))
    print(key, beads)
    return (hv.DynamicMap(fcn, kdims = ['bead']+list(kwa))
            .redim.values(bead = beads, **kwa))

__all__ = ['hv', 'hvops']
