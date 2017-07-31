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
from   .track                   import ExperimentList, Track

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
    def elements(cls, evts, labels, opts):
        "shows overlayed Curve items"
        prec  = opts.pop('precision', None)
        style = dict(size = opts.pop('size', 5))
        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])
        itms = []
        for bead in evts.keys():
            det   = evts.detailed(bead, prec)
            xvals = np.arange(len(det.histogram))*det.binwidth+det.minvalue
            itms.append(hv.Curve((xvals, det.histogram), **opts))

            xvals = [i for i, _ in evts.config.details2output(det)]
            yvals = [itms[-1][i] for i in xvals]
            itms.append(hv.Scatter((xvals, yvals), **opts)(style = style))
            if labels:
                itms[-2].label = f'bead'
                itms[-1].label = f'bead'
        return itms

    @classmethod
    def run(cls, evts, labels, opts):
        "shows overlayed Curve items"
        return hv.Overlay(cls.elements(evts, labels, opts))

    @classmethod
    def hpins(cls, seq, oligos, opts):
        "returns haipin positions"
        opts.setdefault('kdims', ['z'])
        opts.setdefault('vdims', ['events'])
        peaks = {}
        for key, vals in sequences.peaks(seq, oligos):
            xvals = np.repeat(vals['position'], 3)
            yvals = np.concatenate([[(0, 1)[plus], (1, 2)[plus], np.NaN]
                                    for plus in vals['orientation']])
            peaks[key] = hv.Curve((xvals, yvals), label = 'hairpin', **opts)
        return peaks

    @classmethod
    def hpinmap(cls, itms, seq, oligos, labels = None, **opts):
        "creates a DynamicMap with oligos to fit"
        hpins = cls.hpins(seq, oligos, opts)
        def _clone(itm, stretch, bias):
            data = np.copy(itm.data)
            data[:,0] = data[:,0]*stretch+bias
            return itm.clone(data = data)

        # pylint: disable=dangerous-default-value
        def _over(bead, sequence, stretch, bias, cache = [None, ()]):
            if bead != cache[0]:
                cache[0] = bead
                cache[1] = cls.elements(itms[[bead]], labels, opts)
            clones = [_clone(i, stretch, bias) for i in cache[1]]
            return hv.Overlay(clones+[hpins[sequence]])

        beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
        return (hv.DynamicMap(_over, kdims = ['sequence', 'bead', 'stretch', 'bias'])
                .redim.values(bead    = beads, sequence = list(hpins.keys()))
                .redim.range(stretch = (900, 1300), bias = (0, 60)))

@_add(Beads)
def display(self, kdim = 'bead', labels = None, tpe = 'curve', overlay = True, **opts):
    "returns a hv.DynamicMap showing the beads"
    disp = Display.run
    if kdim == 'bead':
        beads = list(set([i for i in self.keys() if self.isbead(i)]))
        def _fcn(bead):
            return disp(self[[bead]], labels, tpe, overlay, opts)
        return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
    return disp(self, labels, tpe, overlay, opts)

@_add(PeaksDict)  # type: ignore
def display(self, # pylint: disable=function-redefined
            kdim = 'bead', labels = None, sequence = None, oligos = None, **opts):
    "returns a hv.DynamicMap showing the beads"
    disp = PeaksDisplay
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
    "shows overlayed Curve items"
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

@_add(Beads, Track, Beads, Cycles, Events)
def beadmap(self:Track, fcn, **kwa):
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    beads = list(self.keys())
    return (hv.DynamicMap(partial(fcn, self), kdims = ['bead']+list(kwa))
            .redim.values(bead = beads, **kwa))

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
