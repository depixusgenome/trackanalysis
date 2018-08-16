#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
from   typing            import List
import numpy             as     np

from   utils.holoviewing import addto, hv
from   ...track          import Bead, FoV

@addto(Bead)        # type: ignore
def display(self, colorbar = True):
    "displays the bead calibration"
    img = np.ones((64,64)) if self.image is None or self.image.size == 0 else self.image
    bnd = [0, 0] + list(img.shape)
    return (hv.Image(img[::-1], bounds = bnd, kdims = ['z focus (pixel)', 'profile'])
            (plot = dict(colorbar = colorbar)))

@addto(FoV)         # type: ignore
def display(self,   # pylint: disable=too-many-arguments
            beads    = None,
            calib    = None,
            cmap     = 'YlGn',
            colorbar = True):
    """
    displays the FoV with bead positions as well as calibration images.
    """
    if calib is None:
        calib = any(x.image is not None and x.image.size != 0
                    for x in self.beads.values())
    bnd   = self.bounds()
    beads = list(self.beads.keys()) if beads is None or beads is Ellipsis else list(beads)
    if len(beads) and np.isscalar(beads[0]):
        beads = (beads,)

    itms  = [hv.Image(self.image[::-1], bounds = bnd)
             (plot  = dict(colorbar = colorbar),
              style = dict(cmap = cmap))]
    for grp in beads:
        if grp is None or grp is Ellipsis:
            grp = list(self.beads.keys())
        good  = {i: j.position[:2] for i, j in self.beads.items() if i in grp}
        xvals = [i                 for i, _ in good.values()]
        yvals = [i                 for _, i in good.values()]
        txt   = [f'{i}'            for i    in good.keys()]
        itms.append(hv.Points((xvals, yvals))(style = dict(size=10, alpha=.6)))
        itms.extend(hv.Text(*i) for i in zip(xvals, yvals, txt))

    top = hv.Overlay(itms).redim(x = 'x (μm)', y = 'y (μm)')
    if not calib:
        return top

    bottom = hv.DynamicMap(lambda bead: self.beads[bead].display(colorbar = colorbar),
                           kdims = ['bead']).redim.values(bead = beads)
    return (top+bottom).cols(1)

__all__: List[str] = []
