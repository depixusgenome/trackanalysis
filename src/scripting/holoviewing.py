#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import copy
import inspect
from   functools            import partial
from   itertools            import chain, repeat
import numpy                as np
import holoviews            as hv
import holoviews.operation  as hvops
from   data.trackitems      import Beads, Cycles
from   eventdetection.data  import Events
from   .track               import ExperimentList, Track

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

@_add(Beads, Cycles)
def curve(self, *keys, labels = None, tpe = hv.Curve, overlay = True):
    "shows overlayed Curve items"
    crvs = list(copy.copy(self).selecting(keys) if len(keys) else self)
    if not overlay:
        crvs = list(chain.from_iterable(zip(crvs, repeat([np.NaN]))))
        return tpe(np.concatenate(crvs))

    opts = dict(kdims = ['frames'], vdims = ['z'])
    if len(crvs) < 3 or labels is True:
        crvs = [tpe(j, label = str(i), **opts)
                for i, j in crvs if np.isfinite(j).sum() > 0]
    else:
        crvs = [tpe(j, **opts) for _, j in crvs if np.isfinite(j).sum() > 0]
    return crvs[0] if len(crvs) == 1 else hv.Overlay(crvs)

@_add(Events)           # type: ignore
def curve(self, *keys,  # pylint: disable=function-redefined
          labels = None, tpe = hv.Curve, overlay = True): # pylint: disable=
    "shows overlayed Curve items"
    crvs = list(copy.copy(self).selecting(keys) if len(keys) else self)
    if not overlay:
        crvs = np.concatenate([i for _, i in crvs])

    conc = lambda x: np.concatenate(list(chain.from_iterable(zip(x, repeat([np.NaN])))))
    vals = lambda x: (conc([np.arange(i[0], i[0]+len(i[1])) for i in x]), conc(x['data']))
    opts = dict(kdims = ['frames'], vdims = ['z'])
    if len(crvs) < 3 or labels is True:
        crvs = [tpe(vals(j), label = str(i), **opts) for i, j in crvs if len(j)]
    else:
        crvs = [tpe(vals(j), **opts) for _, j in crvs if len(j)]

    return crvs[0] if len(crvs) == 1 else hv.Overlay(crvs)

@_add(Beads, Cycles)
def points(self, *keys, labels = None, tpe = hv.Points, overlay = True):
    "shows overlayed Points items"
    return self.curve(*keys, labels = labels, tpe = tpe, overlay = overlay)

@_add(Beads, Track, Beads, Cycles, Events)
def beadmap(self:Track, fcn, **kwa):
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    beads = list(self.keys())
    return (hv.DynamicMap(partial(fcn, self), kdims = ['bead']+list(kwa))
            .redim.values(bead = beads, **kwa))

@_add(Cycles, Events)
def show(self):
    "returns a hv.DynamicMap showing the cycles"
    beads = list(set([i for i, _ in self.keys() if Beads.isbead(i)]))
    def _fcn(bead):
        return self[bead, ...].curve()
    return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)

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
