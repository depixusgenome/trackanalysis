#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
from   typing                   import List
from   functools                import partial
from   copy                     import deepcopy
import numpy                    as     np

from   scripting.holoviewing    import addto, displayhook, BasicDisplay, hv
from   ...track                 import Bead, FoV, Track
from   ...views                 import Beads, Cycles

displayhook(Beads, Cycles)

class Display(BasicDisplay): # pylint: disable=abstract-method
    "displays the beads or cycles"
    _kdim    = 'bead'
    _labels  = None
    _tpe     = 'curve'
    _overlay = False
    _keys    = None
    _stretch = 1.
    _bias    = 0.
    KEYWORDS = BasicDisplay.KEYWORDS | frozenset(locals())
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
        return hv.Overlay([hv.Text(0.5, .9, args[0], kdims = tdims),
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

        if not any(isinstance(i, hv.Text) for i in crvs): # dummy text for warnings
            for i in crvs:
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
    """
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
    """
    def _perbead(self, bead):
        return self._run(self._items[[bead]])

    def _perall(self):
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

@addto(Track, Beads)
def map(self, fcn, **kwa):
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@addto(Cycles)      # type: ignore
def map(self, fcn, kdim = None, **kwa):
    "returns a hv.DynamicMap with beads or cycles, as well as kwargs in the kdims"
    if kdim is None:
        kdim = 'cycle' if ('cycle' in kwa and 'bead' not in kwa) else 'bead'

    if kdim == 'bead':
        kwa.setdefault(kdim, list(set(i for _, i in self.keys())))
    elif kdim == 'cycle':
        kwa.setdefault(kdim, list(set(i for i, _ in self.keys())))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@addto(Bead)        # type: ignore
def display(self, colorbar = True):
    "displays the bead calibration"
    if self.image is None:
        return

    bnd = [0, 0] + list(self.image.shape)
    return (hv.Image(self.image[::-1], bnd, kdims = ['z focus (pixel)', 'profile'])
            (plot = dict(colorbar = colorbar)))

@addto(FoV)         # type: ignore
def display(self,   # pylint: disable=too-many-arguments
            beads    = None,
            calib    = True,
            colorbar = True,
            ptcolor  = 'lightblue',
            txtcolor = 'blue'):
    """
    displays the FoV with bead positions as well as calibration images.
    """
    bnd = self.bounds()
    beads = list(self.beads.keys()) if beads is None else list(beads)

    good  = {i: j.position[:2] for i, j in self.beads.items() if i in beads}
    xvals = [i                 for i, _ in good.values()]
    yvals = [i                 for _, i in good.values()]
    txt   = [f'{i}'            for i    in good.keys()]

    top   = (hv.Overlay([hv.Image(self.image[::-1], bnd)(plot = dict(colorbar = colorbar)),
                         hv.Points((xvals, yvals))(style = dict(color = ptcolor))]
                        +[hv.Text(*i)(style = dict(color = txtcolor))
                          for i in zip(xvals, yvals, txt)])
             .redim(x = 'x (μm)', y = 'y (μm)'))
    if not calib:
        return top
    bottom = hv.DynamicMap(lambda bead: self.beads[bead].display(colorbar = colorbar),
                           kdims = ['bead']).redim.values(bead = beads)
    return (top+bottom).cols(1)

__all__: List[str] = []
