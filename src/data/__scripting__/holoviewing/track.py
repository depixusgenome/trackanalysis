#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=redefined-builtin,function-redefined
"""
Adds shortcuts for using holoview
"""
from   typing                   import List
import pandas                   as     pd

from   scripting.holoviewing    import addto, hv, addproperty
from   ...track                 import Bead, FoV, Secondaries

@addto(Bead)        # type: ignore
def display(self, colorbar = True):
    "displays the bead calibration"
    if self.image is None:
        return

    bnd = [0, 0] + list(self.image.shape)
    return (hv.Image(self.image[::-1], bounds = bnd, kdims = ['z focus (pixel)', 'profile'])
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

    top   = (hv.Overlay([hv.Image(self.image[::-1], bounds = bnd)
                         (plot = dict(colorbar = colorbar)),
                         hv.Points((xvals, yvals))
                         (style = dict(color = ptcolor))]
                        +[hv.Text(*i)(style = dict(color = txtcolor))
                          for i in zip(xvals, yvals, txt)])
             .redim(x = 'x (μm)', y = 'y (μm)'))
    if not calib:
        return top
    bottom = hv.DynamicMap(lambda bead: self.beads[bead].display(colorbar = colorbar),
                           kdims = ['bead']).redim.values(bead = beads)
    return (top+bottom).cols(1)

@addproperty(Secondaries) # type: ignore
class SecondariesDisplay:
    "Displays temperatures or vcap"
    def __init__(self, val):
        self.sec = val

    def temperatures(self):
        "displays the bead calibration"
        get = lambda i, j: getattr(self.sec, i)[j]
        fcn = lambda i, j: hv.Curve((get(i, 'index'), get(i, 'value')),
                                    'image id', '°C', label = j)
        return fcn('tservo', 'T° Servo')*fcn('tsink', 'T° Sink')*fcn('tsample', 'T° Sample')

    def vcap(self):
        "displays the bead calibration"
        vca   = self.sec.vcap
        frame = pd.DataFrame({'image': vca['index'], 'zmag': vca['zmag'], 'vcap': vca['vcap']})
        return hv.Scatter(frame, 'zmag', ['vcap', 'image'])

__all__: List[str] = []
