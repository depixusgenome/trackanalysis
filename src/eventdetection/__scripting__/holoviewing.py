#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
from   typing                import List, cast
from   functools             import partial
import numpy                 as     np
from   scripting.holoviewing import addto, addproperty, hv

from   model.__scripting__                          import Tasks
from   data.__scripting__                           import TracksDict
from   data.__scripting__.holoviewing.trackviews    import CycleDisplay
from   data.__scripting__.holoviewing.tracksdict    import TracksDictDisplay

from   ..data                                       import Events

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

@addto(Events)
def map(self, fcn, kdim = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap with beads or cycles, as well as kwargs in the kdims"
    if kdim is None:
        kdim = 'cycle' if ('cycle' in kwa and 'bead' not in kwa) else 'bead'

    if kdim == 'bead':
        kwa.setdefault(kdim, list(set(i for _, i in self.keys())))
    elif kdim == 'cycle':
        kwa.setdefault(kdim, list(set(i for i, _ in self.keys())))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@addproperty(TracksDict, 'events')
class EventTracksDictDisplay(TracksDictDisplay):
    "tracksdict display for events"
    _name = cast(str, property(lambda _: 'events', lambda _1, _2: None))
    def dataframe(self, *tasks, **kwa):
        "creates a dataframe for all keys"
        return self._items.dataframe(Tasks.eventdetection, *tasks, **kwa)

__all__: List[str] = []
