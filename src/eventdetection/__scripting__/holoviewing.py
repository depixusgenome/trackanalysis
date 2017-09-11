#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   typing           import List, Type
from   functools        import partial
import numpy            as np
from   utils.decoration import addto
from   ..data           import Events

def _get(name, attr = None):
    mod = sys.modules[name]
    return mod if attr is None else getattr(mod, attr)

# pylint: disable=invalid-name
hv                   = _get('holoviews')
TracksDict: Type     = _get('data.__scripting__', 'TracksDict')
Display:    Type     = _get('data.__scripting__.holoviewing', 'Display')
TracksDictDisplay: Type = _get('data.__scripting__.holoviewing.tracksdict',
                               'TracksDictDisplay')

class EventDisplay(Display): # type: ignore
    "displays the events"
    @classmethod
    def run(cls, itms, labels, tpe, overlay, opts): # pylint: disable=too-many-arguments
        "shows overlayed Curve items"
        vals = lambda x: (cls.concat([np.arange(i[0], i[0]+len(i[1])) for i in x]),
                          cls.concat(x['data']))

        try:
            good = tuple((i, vals(j)) for i, j in itms if len(j))
        except Exception as exc: # pylint: disable=broad-except
            return cls.errormessage(exc,
                                    x = opts.get('kdims', ['frames'])[0],
                                    y = opts.get('vdims', ['z'])[0])

        if not overlay:
            good = (('', (cls.concat(i[0] for _, i in good),
                          cls.concat(i[1] for _, i in good))),)
        return cls._create(labels, tpe, overlay, opts, good)

@addto(Events)   # type: ignore
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
    return EventDisplay.cycles(self, kdim, labels, tpe, overlay, **opts)

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

@addto(TracksDict) # type: ignore
def events(self, overlay = None, reference = None, **kwa):
    """
    A hv.DynamicMap showing events

    Options are:

        * *overlay* == 'key': for a given bead, all tracks are overlayed
        The *reference* option can be used to indicate the top-most track.
        * *overlay* == 'bead': for a given track, all beads are overlayed
        The *reference* option can be used to indicate the top-most bead.
        * *overlay* == None:

            * *reference*: the reference is removed from the *key* widget and
            allways displayed to the left independently.
            * *refdims*: if set to *True*, the reference gets its own dimensions.
            Thus zooming and spanning is independant.
            * *reflayout*: can be set to 'top', 'bottom', 'left' or 'right'
    """
    return TracksDictDisplay.run(self, 'events', overlay, reference, kwa)

__all__: List[str] = []