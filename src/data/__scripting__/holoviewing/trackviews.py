#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
from   typing            import List, Union
from   copy              import deepcopy
import pandas            as     pd
import numpy             as     np

from   model.level       import PHASE
from   utils.holoviewing import displayhook, BasicDisplay, hv
from   ...views          import Beads, Cycles

displayhook(Beads, Cycles)

class Display(BasicDisplay): # pylint: disable=abstract-method
    "displays the beads or cycles"
    _kdim                      = 'bead'
    _labels  : Union[str,bool] = None
    _tpe                       = 'curve'
    _overlay                   = False
    _keys                      = None
    _stretch                   = 1.
    _bias                      = 0.
    _alpha                     = 1.
    KEYWORDS                   = BasicDisplay.KEYWORDS | frozenset(locals())
    def __init__(self, items, **opts):
        super().__init__(items, **opts)
        if isinstance(self._tpe, str):
            self._tpe = (getattr(hv, self._tpe) if hasattr(hv, self._tpe) else
                         getattr(hv, self._tpe.capitalize()))

    def __getitem__(self, value):
        self._keys = value if isinstance(value, list) else [value]

    @staticmethod
    def graphdims():
        "returns the dimension names"
        return {'kdims': ['frames'], 'vdims': ['z']}

    def errormessage(self, exc):
        "displays error message"
        args = getattr(exc, 'args', tuple())
        if not (isinstance(args, (list, tuple)) and len(args) == 2):
            return None

        opts  = self.graphdims()
        opts.update(self._opts)
        cdims = {i: opts[i] for i in ('kdims', 'vdims') if i in opts}
        tdims = (cdims['kdims']+opts.get('vdims', []))[:2]
        return hv.Overlay([hv.Text(0.5, .9, str(args[0]), kdims = tdims),
                           self._tpe(([0., np.NaN, 1.],[0., np.NaN, 1.]),
                                     **cdims)])

    def _create(self, opts, good):
        opts = deepcopy(opts)
        for i, j in self.graphdims().items():
            opts.setdefault(i, j)

        if isinstance(self._labels, str):
            crvs = [self._tpe(j, label = self._labels, **opts) for i, j in good]
        elif (len(good) < 3 and self._labels) or self._labels is True:
            crvs = [self._tpe(j, label = f'{i}', **opts) for i, j in good]
        else:
            crvs = [self._tpe(j, **opts) for _, j in good]

        if 0. <  self._alpha < 1.:
            crvs = [i(style = dict(alpha = self._alpha)) for i in crvs]

        if not any(isinstance(i, hv.Text) for i in crvs): # dummy text for warnings
            for i in crvs:
                if isinstance(i.data, pd.DataFrame):
                    continue
                val = next(((j[0], j[1]) for j in i.data if np.isnan(j).sum() == 0), None)
                if val is not None:
                    break
            else:
                val = .5, 5.
            crvs.insert(0, hv.Text(*val, '', kdims = [opts['kdims'][0], opts['vdims'][0]]))
        return hv.Overlay(crvs)

    def _run(self, itms): # pylint: disable=too-many-arguments
        "shows overlayed Curve items"
        opts    = deepcopy(self._opts)
        stretch = self._stretch
        bias    = self._bias
        try:
            good = tuple((i, (j-bias)*stretch) for i, j in itms if np.any(np.isfinite(j)))
        except KeyError as exc: # pylint: disable=broad-except
            txt  = f'Missing {self.config("kdim")} {exc.args[0]}'
            return self.errormessage(KeyError(txt, 'warning'))
        except Exception as exc: # pylint: disable=broad-except
            ret  = self.errormessage(exc)
            if ret is None:
                raise
            return ret

        if not self._overlay:
            if len(good):
                good = (('', (self.concat(np.arange(len(i), dtype = 'f4') for _, i in good),
                              self.concat(i for _, i in good))),)
            else:
                good = (('', (np.ones(0, dtype = 'f4'), np.ones(0, dtype = 'f4'))),)
        return self._create(opts, good)

class CycleDisplay(Display, display = Cycles):
    """
    Displays cycles.

    Options are:

    * *kdim*: if set to 'bead', then a *holoviews.DynamicMap* is returned,
    displaying beads independently. If set to 'cycle', the map displays cycles
    independently.
    * *labels*: if *False*, no labels are added. If *None*, labels are added
    if 3 or less beads are shown.
    * *tpe*: can be scatter or curve.
    * *overlay*: if *False*, all data is concatenated into one array.
    * *stretch*: applies a stretch to z values
    * *bias*: applies a bias to z values
    * *alpha*: applies an alpha to all curves
    """
    _alpha = .1
    def _percycle(self, cyc):
        return self._run(self._items[..., cyc])

    def _perbead(self, bead):
        return self._run(self._items[bead, ...])

    def _perall(self):
        return self._run(self._items)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return getattr(self, '_per'+str(self._kdim), self._perall)

    def getredim(self):
        "Returns the keys used by the dynamic map"
        kdim = self._kdim
        if kdim is not None and self._keys:
            return self._keys

        itms = self._items
        if kdim == 'cycle':
            return ((kdim, list(set([i for _, i in itms.keys() if Beads.isbead(_)]))),)
        if kdim == 'bead':
            return ((kdim, list(set([i for i, _ in itms.keys() if Beads.isbead(i)]))),)
        return None

class BeadDisplay(Display, display = Beads):
    """
    Displays beads.

    Attributes are:

    * *kdim*: if 'bead', then a *holoviews.DynamicMap* is returned, displaying
    beads independently.
    * *labels*: if *False*, no labels are added. If *None*, labels are added
    if 3 or less beads are shown.
    * *tpe*: can be scatter or curve.
    * *overlay*: if *False*, all data is concatenated into one array.
    * *area*: Areas are used instead of curves, 1 measure per cycle. If astime
    is true, the x axis is time.
    """
    _area    = False
    _astime  = None
    _phases  = PHASE.relax, PHASE.pull
    KEYWORDS = Display.KEYWORDS | frozenset(locals())
    def _perbead(self, bead):
        crv = self._run(self._items[[bead]])
        if self._area:
            cyc   = (self._items[...,...]
                     .withdata({0: tuple(crv)[-1].data[:,1]})
                     .withaction(lambda _, i: (i[0], np.nanmedian(i[1]))))
            ylow  = np.array(list(cyc.withphases(self._phases[0]).values()), dtype = 'f4')
            yhigh = np.array(list(cyc.withphases(self._phases[1]).values()), dtype = 'f4')
            if self._astime:
                xvals = self._items.track.phase.select(..., 0)/self._items.track.framerate
                dur   = hv.Dimension("duration", unit = self._astime)
                if self._astime == 'h':
                    xvals /= 3600.
                elif self._astime == 'd':
                    xvals /= 86400.
                frame = pd.DataFrame(dict(duration = xvals, zlow = ylow, z = yhigh))
            else:
                xvals = np.arange(len(ylow), dtype = 'f4')
                frame = pd.DataFrame(dict(cycles = xvals, zlow = ylow, z = yhigh))
                dur   = 'cycles'
            return hv.Area(frame, dur, ["z", "zlow"])*tuple(crv)[0]
        return crv

    def _perall(self):
        if self._area:
            keys = self._keys if self._keys else self._items.beads.keys()
            return hv.Overlay([self._perbead(i) for i in keys])
        return self._run(self._items)

    def getmethod(self):
        "Returns the method used by the dynamic map"
        return getattr(self, '_per'+str(self._kdim), self._perall)

    def getredim(self):
        "Returns the keys used by the dynamic map"
        if self._kdim is not None and self._keys:
            return self._keys
        if self._kdim == 'bead':
            return ((self._kdim, list(set([i for i in self._items.keys()
                                           if self._items.isbead(i)]))),)
        return None
__all__: List[str] = []
