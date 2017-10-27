#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                import List, Type
from   functools             import partial
import numpy                 as     np
from   scripting.holoviewing import addto, addproperty
from   ..data                import Events

def _get(name, attr = None):
    mod = sys.modules[name]
    return mod if attr is None else getattr(mod, attr)

# pylint: disable=invalid-name
hv                      = _get('holoviews')
CycleDisplay:      Type = _get('data.__scripting__.holoviewing.trackviews', 'CycleDisplay')
TracksDict:        Type = _get('data.__scripting__', 'TracksDict')
TracksDictDisplay: Type = _get('data.__scripting__.holoviewing.tracksdict',
                               'TracksDictDisplay')

class EventDisplay(CycleDisplay, display = Events): # type: ignore
    """
    Displays cycles.

    Attributes are:

    * *kdim*: if set to 'bead', then a *holoviews.DynamicMap* is returned,
    displaying beads independently. If set to 'cycle', the map displays cycles
    independently.
    * *labels*: if *False*, no labels are added. If *None*, labels are added
    if 3 or less beads are shown.
    * *tpe*: can be scatter or curve.
    * *overlay*: if *False*, all data is concatenated into one array.
    """
    def _run(self, itms):
        "shows overlayed Curve items"
        opts    = dict(self._opts)
        stretch = opts.pop('stretch', 1.)
        bias    = opts.pop('bias',    0.)
        overlay = self._overlay

        vals = lambda x: (self.concat([np.arange(i[0], i[0]+len(i[1])) for i in x]),
                          (self.concat(x['data'])-bias)*stretch)
        try:
            if overlay in (all, Ellipsis):
                good = [] # type: ignore
                for i, j in itms:
                    if len(j):
                        good.extend((i, (np.arange(k[0], k[0]+len(k[1])),
                                         (k[1]-bias)*stretch))
                                    for k in j)
                overlay = True
                good    = tuple(good)
            else:
                good    = tuple((i, vals(j)) for i, j in itms if len(j))
        except Exception as exc: # pylint: disable=broad-except
            return self.errormessage(exc)

        if not overlay:
            if len(good):
                good = (('', (self.concat(i[0] for _, i in good),
                              self.concat(i[1] for _, i in good))),)
            else:
                good = (('', (np.ones(0, dtype = 'f4'), np.ones(0, dtype = 'f4'))),)

        return self._create(opts, good)

@addto(Events)  # type: ignore
def map(self, fcn, kdim = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap with beads or cycles, as well as kwargs in the kdims"
    if kdim is None:
        kdim = 'cycle' if ('cycle' in kwa and 'bead' not in kwa) else 'bead'

    if kdim == 'bead':
        kwa.setdefault(kdim, list(set(i for _, i in self.keys())))
    elif kdim == 'cycle':
        kwa.setdefault(kdim, list(set(i for i, _ in self.keys())))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

addproperty(TracksDict, 'events', name = 'events', prop = TracksDictDisplay)

__all__: List[str] = []
