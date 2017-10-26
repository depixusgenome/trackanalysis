#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   abc                   import ABC, abstractmethod
from   itertools             import chain, repeat
from   copy                  import deepcopy
import numpy                 as     np

from   scripting.holoviewing import displayhook
from   ...                   import Beads

hv    = sys.modules['holoviews']  # pylint: disable=invalid-name

@displayhook
class BasicDisplay(ABC):
    "Everything needed for creating a dynamic map display"
    KEYWORDS = frozenset(locals())
    def __init__(self, items, **opts):
        self._items   = items
        for i in self.KEYWORDS:
            setattr(self, i, opts.pop(i[1:], getattr(self.__class__, i)))
        self._opts    = opts

    def __add__(self, other):
        return self.display() + (other if isinstance(other, hv.Element) else other.display())

    def __mul__(self, other):
        return self.display() * (other if isinstance(other, hv.Element) else other.display())

    def __lshift__(self, other):
        return self.display() << (other if isinstance(other, hv.Element) else other.display())

    def __rshift__(self, other):
        return self.display() >> (other if isinstance(other, hv.Element) else other.display())

    def config(self, name = ...):
        "returns the config"
        cnf = deepcopy(self._opts)
        cnf.update({i[1:]: deepcopy(j) for i, j in self.__dict__.items()
                    if (i not in ('_opts', '_items') and
                        len(i) > 2 and i[0] == '_'   and
                        i[1].lower() == i[1])})
        return cnf if name is Ellipsis else cnf[name]

    def __call__(self, **opts):
        default = self.__class__(self._items).config()
        config  = {i: j for i, j in self.config().items() if j != default[i]}
        config.update(opts)
        return self.__class__(self._items, **config)

    @staticmethod
    def concat(itr):
        "concatenates arrays, appending a NaN"
        return np.concatenate(list(chain.from_iterable(zip(itr, repeat([np.NaN])))))

    def display(self, **kwa):
        "displays the cycles using a dynamic map"
        this = self(**kwa) if kwa else self
        fcn  = this.getmethod()
        keys = this.getredim()
        if keys is None:
            return fcn()

        itr   = getattr(keys, 'items', lambda : keys)
        kdims = [i                      for i, _ in itr()]
        vals  = [(i, j)                 for i, j in itr() if isinstance(j, list)]
        rngs  = [(i, (j.start, j.stop)) for i, j in itr() if isinstance(j, slice)]
        done  = set(dict(vals)) | set(dict(rngs))
        sels  = [(i, [j])               for i, j in itr() if i not in done]
        return (hv.DynamicMap(fcn, kdims = kdims)
                .redim.values(**dict(vals), **dict(sels))
                .redim.range(**dict(rngs)))

    @abstractmethod
    def getmethod(self):
        "Returns the method used by the dynamic map"

    @abstractmethod
    def getredim(self):
        "Returns the keys used by the dynamic map"

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

class CycleDisplay(Display):
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

class BeadDisplay(Display):
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
