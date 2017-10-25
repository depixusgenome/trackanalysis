#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Adds shortcuts for using holoview
"""
import sys
from   typing                   import List
from   functools                import partial
from   scripting.holoviewing    import addto
from   .display                 import CycleDisplay, BeadDisplay
from   ...track                 import Bead, FoV, Track
from   ...views                 import Beads, Cycles

hv    = sys.modules['holoviews']  # pylint: disable=invalid-name

@addto(Beads) # type: ignore
@property
def display(self):                      # pylint: disable=function-redefined
    "Displays beads"
    return BeadDisplay(self)

@addto(Cycles)                          # type: ignore
@property
def display(self):                      # pylint: disable=function-redefined
    "Displays cycles."
    return CycleDisplay(self)

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

@addto(Bead)       # type: ignore
def display(self,  # pylint: disable=function-redefined
            colorbar = True):
    "displays the bead calibration"
    if self.image is None:
        return

    bnd = [0, 0] + list(self.image.shape)
    return (hv.Image(self.image[::-1], bnd, kdims = ['z focus (pixel)', 'profile'])
            (plot = dict(colorbar = colorbar)))

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
             .redim(x = 'x (μm)', y = 'y (μm)'))
    if not calib:
        return top
    bottom = hv.DynamicMap(lambda bead: self.beads[bead].display(colorbar = colorbar),
                           kdims = ['bead']).redim.values(bead = beads)
    return (top+bottom).cols(1)

__all__: List[str] = []
