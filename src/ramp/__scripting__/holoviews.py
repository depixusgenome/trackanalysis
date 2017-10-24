#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Adds shortcuts for using holoview"
import sys
import numpy                    as np
from   scripting.holoviewing    import addto, displayhook
from   data.track               import Track, isellipsis

hv = sys.modules['holoviews']  # pylint: disable=invalid-name

@displayhook
class RampDisplay:
    "displays rams"
    def __init__(self, track):
        self.track  = track
        self.beads  = None
        self.cycles = None

    def __getitem__(self, values):
        if isinstance(values, int):
            self.beads = [values]
        elif isinstance(values, list):
            self.beads = values
        elif isinstance(values, tuple):
            beads, cycles = values
            self.beads  = (None     if isellipsis(beads)       else
                           [beads]  if isinstance(beads, int)  else
                           beads)
            self.cycles = (None     if isellipsis(cycles)      else
                           [cycles] if isinstance(cycles, int) else
                           cycles)

    def _action(self, cycles, align, length, stretch, bias): # pylint: disable=too-many-arguments
        if cycles is None:
            cycles = ... if self.cycles is None else self.cycles

        items = self.track.cycles
        zmag  = {i[1]: j for i, j in items['zmag', cycles]}

        if align.lower() == 'first':
            imax = dict.fromkeys(zmag.keys(), slice(length))        # type: ignore
        elif align.lower() == 'last':
            imax  = dict.fromkeys(zmag.keys(), slice(-length,0))    # type: ignore
        elif align.lower() == 'max':
            maxes = {i: int(.1+np.median((j == np.nanmax(j)).nonzero()[0]))
                     for i, j in zmag.items()}
            imax  = {i: slice(max(0, j-length//2), j+length//2) for i, j in maxes.items()}
        else:
            imax  = None

        def _show(bead):
            data = {i[1]: j for i, j in items[bead,cycles]}
            if imax:
                data = {i: data[i] - np.nanmean(data[i][j]) for i, j in imax.items()}

            zero = np.nanmedian([np.nanmean(j[:length]) for j in data.values()])
            for j in data.values():
                j[:] = (j-zero-bias)*stretch

            return hv.Overlay([hv.Curve((zmag[i], data[i]),
                                        label = f'cycle {i}',
                                        kdims = ['zmag'],
                                        vdims = ['z'])
                               for i in data])
        return _show

    def display(self, beads = None, cycles = None, # pylint: disable=too-many-arguments
                align   = 'max', alignmentlength = 5,
                stretch = 1.,    bias            = 0.,
                legend  = 'left'):
        """
        Displays ramps

        Keywords are:

        * *beads*: the list of bead to display
        * *cycles*: the list of cycles to display
        * *align*: can be

            * *first*:   align all cycles on their 1st values
            * *last*:  align all cycles on their last values
            * *max*:    align all cycles around their *zmag* max position
            * *None*: don't align cycles

        * *alignmentlength*: if *align* is not *None*, will use this number of
        frames for aligning cycles
        * *legend*: legend position, *None* for no legend
        """
        if isellipsis(beads):
            beads = self.track.beadsonly.keys()
        elif beads is None:
            beads = self.track.beadsonly.keys() if self.beads is None else self.beads

        dmap = hv.DynamicMap(self._action(cycles, align, alignmentlength, stretch, bias),
                             kdims = ['bead'])
        dmap = dmap.redim.values(bead = list(beads))
        return dmap(plot = (dict(legend_position = legend) if legend else
                            dict(show_legend     = False)))

@addto(Track) # type: ignore
@property
def ramp(self):
    "displays ramps"
    return RampDisplay(self)

__all__ = [] # type: list
