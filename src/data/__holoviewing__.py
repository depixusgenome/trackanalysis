#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                   import List
from   functools                import partial
from   itertools                import chain, repeat
import numpy                    as np
from   utils.decoration         import addto
from   utils.logconfig          import getLogger
from   .track                   import FoV, Bead
from   .trackitems              import Beads, Cycles

from   .__scripting__           import ExperimentList, Track, TracksDict

LOGS  = getLogger(__name__)
hv    = sys.modules['holoviews']  # pylint: disable=invalid-name
Tasks = sys.modules['model.__scripting__'].Tasks

class Display:
    "displays the beads or cycles"
    @staticmethod
    def concat(itr):
        "concatenates arrays, appending a NaN"
        return np.concatenate(list(chain.from_iterable(zip(itr, repeat([np.NaN])))))

    @staticmethod
    def errormessage(exc, **dims):
        "displays error message"
        args = getattr(exc, 'args', tuple())
        if isinstance(args, (list, tuple)) and len(args) == 2:
            txt = str(exc.args[0]).split('\n')
        else:
            raise RuntimeError("error") from exc

        ovr = hv.Overlay([hv.Text(0.4, len(txt)*.1+.5-i*.1, j)
                          for i, j in enumerate(txt)])
        return ovr.redim(**dims) if len(dims) else ovr

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
        try:
            good = tuple((i, j) for i, j in itms if np.any(np.isfinite(j)))
        except Exception as exc: # pylint: disable=broad-except
            return cls.errormessage(exc,
                                    x = opts.get('kdims', ['frames'])[0],
                                    y = opts.get('vdims', ['z'])[0])

        if not overlay:
            good = (('', (cls.concat(np.arange(len(i), dtype = 'f4') for _, i in good),
                          cls.concat(i for _, i in good))),)
        return cls._create(labels, tpe, overlay, opts, good)

    @classmethod
    def cycles(cls, itms, # pylint: disable=too-many-arguments
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
        disp = cls.run
        if kdim == 'cycle':
            keys = list(set([i for _, i in itms.keys() if Beads.isbead(_)]))
            def _percycle(cyc):
                return disp(itms[...,cyc], labels, tpe, overlay, opts)
            fcn  = _percycle
        elif kdim == 'bead':
            keys = list(set([i for i, _ in itms.keys() if Beads.isbead(i)]))
            def _perbead(bead):
                return disp(itms[bead,...], labels, tpe, overlay, opts)
            fcn  = _perbead
        else:
            return disp(itms, labels, tpe, overlay, opts)

        return hv.DynamicMap(fcn, kdims = [kdim]).redim.values(**{kdim: keys})

    @classmethod
    def beads(cls, itms, # pylint: disable=too-many-arguments
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
        disp = cls.run
        if kdim == 'bead':
            beads = list(set([i for i in itms.keys() if itms.isbead(i)]))
            def _fcn(bead):
                return disp(itms[[bead]], labels, tpe, overlay, opts)
            return hv.DynamicMap(_fcn, kdims = ['bead']).redim.values(bead = beads)
        return disp(itms, labels, tpe, overlay, opts)

@addto(Beads)
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
    return Display.beads(self, kdim, labels, tpe, overlay, **opts)

@addto(Cycles)                          # type: ignore
def display(self,                       # pylint: disable=function-redefined
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
    return Display.cycles(self, kdim, labels, tpe, overlay, **opts)

@addto(Track, Beads)
def map(self, fcn, **kwa):              # pylint: disable=redefined-builtin
    "returns a hv.DynamicMap with beads and kwargs in the kdims"
    kwa.setdefault('bead', list(i for i in self.keys()))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@addto(Cycles)                          # type: ignore
def map(self, fcn, kdim = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap with beads or cycles, as well as kwargs in the kdims"
    if kdim is None:
        kdim = 'cycle' if ('cycle' in kwa and 'bead' not in kwa) else 'bead'

    if kdim == 'bead':
        kwa.setdefault(kdim, list(set(i for _, i in self.keys())))
    elif kdim == 'cycle':
        kwa.setdefault(kdim, list(set(i for i, _ in self.keys())))
    return hv.DynamicMap(partial(fcn, self), kdims = list(kwa)).redim.values(**kwa)

@addto(TracksDict)         # type: ignore
def map(self, fcn, kdim = 'oligo', *extra, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap"
    if kdim is not None and kdim not in kwa:
        kwa[kdim] = list(self.keys())

    if 'bead' not in kwa:
        kwa['bead'] = self.keys(*kwa.get(kdim, ()))

    return hv.DynamicMap(fcn, kdims = list(kwa)+list(extra)).redim.values(**kwa)

def _display(self, name, overlay, kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap showing cycles"
    kdims = dict()
    kdims['key']  = kwa.pop('key')  if 'key'  in kwa else list(self.keys())
    kdims['bead'] = kwa.pop('bead') if 'bead' in kwa else list(self.beads(*kdims['key']))

    fcn = lambda key, bead: getattr(self[key], name).display(**kwa)[bead]
    if overlay == 'bead':
        if 'labels' not in kwa:
            fcn = lambda key, bead: (getattr(self[key], name)
                                     .display(labels = f'{key}', **kwa)
                                     [bead])
        def _allbeads(key):
            return hv.Overlay([fcn(key, i) for i in kdims['bead']])
        return hv.DynamicMap(_allbeads, kdims = ['key']).redim.values(key = kdims['key'])

    if overlay == 'key':
        if 'labels' not in kwa:
            fcn = lambda key, bead: (getattr(self[key], name)
                                     .display(labels = f'{key}', **kwa)
                                     [bead])
        def _allkeys(bead):
            return hv.Overlay([fcn(i, bead) for i in kdims['key']])
        return hv.DynamicMap(_allkeys, kdims = ['bead']).redim.values(bead = kdims['bead'])

    fcn = lambda key, bead: getattr(self[key], name).display(**kwa)[bead]
    return hv.DynamicMap(fcn, kdims = ['bead', 'key']).redim.values(**kdims)

@addto(TracksDict)                              # type: ignore
def cycles(self, overlay = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap showing cycles"
    return _display(self, 'cycles', overlay, kwa)

@addto(TracksDict)                                # type: ignore
def measures(self, overlay = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap showing measures"
    return _display(self, 'measures', overlay, kwa)

@addto(TracksDict)                              # type: ignore
def events(self, overlay = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap showing events"
    return _display(self, 'events', overlay, kwa)

@addto(TracksDict)                             # type: ignore
def peaks(self, overlay = None, **kwa): # pylint: disable=redefined-builtin,function-redefined
    "returns a hv.DynamicMap showing peaks"
    return _display(self, 'peaks', overlay, kwa)

@addto(ExperimentList)
def oligomap(self:ExperimentList, oligo, fcn, **kwa):
    "returns a hv.DynamicMap with oligos and beads in the kdims"
    oligos = self.allkeys(oligo)
    beads  = self.available(*oligos)
    LOGS.info(f"{oligos}, {beads}")
    return (hv.DynamicMap(fcn, kdims = ['oligo', 'bead'] + list(kwa))
            .redim.values(oligo = oligos, bead = beads, **kwa))

@addto(ExperimentList)
def keymap(self:ExperimentList, key, fcn, **kwa):
    "returns a hv.DynamicMap with keys in the kdims"
    beads  = self.available(*self.convert(key))
    LOGS.info(f"{key}, {beads}")
    return (hv.DynamicMap(fcn, kdims = ['bead']+list(kwa))
            .redim.values(bead = beads, **kwa))

@addto(FoV)        # type: ignore
def display(self,  # pylint: disable=function-redefined,too-many-arguments
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
             .redim(x = 'x (nm)', y = 'y (nm)'))
    if not calib:
        return top
    bottom = hv.DynamicMap(lambda bead: self.beads[bead].display(colorbar = colorbar),
                           kdims = ['bead']).redim.values(bead = beads)
    return (top+bottom).cols(1)


@addto(Bead)       # type: ignore
def display(self,  # pylint: disable=function-redefined
            colorbar = True):
    "displays the bead calibration"
    if self.image is None:
        return

    bnd = [0, 0] + list(self.image.shape)
    return (hv.Image(self.image[::-1], bnd, kdims = ['z focus (pixel)', 'profile'])
            (plot = dict(colorbar = colorbar)))

__all__: List[str] = []
