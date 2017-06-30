#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import copy
import inspect
from   itertools            import chain, repeat
import numpy                as np
import holoviews            as hv
import holoviews.operation  as hvops
from   data.trackitems      import Beads, Cycles
from   eventdetection.data  import Events

if 'ipykernel_launcher' in inspect.stack()[-3].filename:
    try:
        import bokeh.io as _io
        _io.output_notebook()
        hv.notebook_extension('bokeh')
        from IPython import get_ipython
        get_ipython().magic('output size=150')
    except:                                         # pylint: disable=bare-except
        pass

def curve(self, *keys, labels = None, tpe = hv.Curve, overlay = True):
    "shows overlayed Curve items"
    crvs = list(copy.copy(self).selecting(keys) if len(keys) else self)
    if not overlay:
        crvs = list(chain.from_iterable(zip(crvs, repeat([np.NaN]))))
        return tpe(np.concatenate(crvs))

    if len(crvs) < 3 or labels is True:
        crvs = [tpe(j, label = str(i)) for i, j in crvs if np.isfinite(j).sum() > 0]
    else:
        crvs = [tpe(j) for _, j in crvs if np.isfinite(j).sum() > 0]
    return crvs[0] if len(crvs) == 1 else hv.Overlay(crvs)

def points(self, *keys, labels = None, tpe = hv.Points, overlay = True):
    "shows overlayed Points items"
    return self.curve(*keys, labels = labels, tpe = tpe, overlay = overlay)

Beads .curve  = curve
Beads .points = points
Cycles.curve  = curve
Cycles.points = points

def evtcurve(self, *keys, labels = None, tpe = hv.Curve, overlay = True):
    "shows overlayed Curve items"
    crvs = list(copy.copy(self).selecting(keys) if len(keys) else self)
    if not overlay:
        crvs = np.concatenate([i for _, i in crvs])

    conc = lambda x: np.concatenate(list(chain.from_iterable(zip(x, repeat([np.NaN])))))
    vals = lambda x: (conc([np.arange(i[0], i[0]+len(i[1])) for i in x]), conc(x['data']))
    if len(crvs < 3) or labels is True:
        crvs = [tpe(vals(j), label = str(i)) for i, j in crvs]
    else:
        crvs = [tpe(vals(j)) for _, j in crvs]

    return crvs[0] if len(crvs) == 1 else hv.Overlay(crvs)

Events.curve  = evtcurve
Events.points = points

__all__ = ['hv', 'hvops']
